import os
import io
import json
import re
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
from supabase import create_client
import anthropic
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

load_dotenv()

app = Flask(__name__)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = None
if supabase_url and supabase_key and supabase_url != "your_supabase_url_here":
    supabase = create_client(supabase_url, supabase_key)

anthropic_key = os.getenv("ANTHROPIC_API_KEY")
claude = None
if anthropic_key:
    claude = anthropic.Anthropic(api_key=anthropic_key)


def extract_json(text):
    """Extract a JSON object from Claude's response, handling markdown fences and preamble text."""
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    # Find the first { and last } to extract the JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def modify_recipe_with_ai(recipe_text, allergies, taste_preferences, ingredient_limitations, equipment_limitations, scaling="1"):
    """Call Claude API to generate a modified recipe based on criteria."""
    if not claude:
        return None

    criteria_parts = []
    if allergies:
        criteria_parts.append(f"Allergies: {allergies}")
    if taste_preferences:
        criteria_parts.append(f"Taste preferences: {taste_preferences}")
    if ingredient_limitations:
        criteria_parts.append(f"Ingredient limitations: {ingredient_limitations}")
    if equipment_limitations:
        criteria_parts.append(f"Equipment limitations: {equipment_limitations}")
    if scaling and scaling not in ("1", "1x"):
        criteria_parts.append(f"Recipe scaling: {scaling}")

    criteria_text = "\n".join(criteria_parts) if criteria_parts else "No specific criteria provided."

    user_message = f"""Here is the original recipe:

{recipe_text}

Please modify this recipe based on the following criteria:
{criteria_text}"""

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system="You are a professional baker and recipe developer. The user will give you a recipe and modification criteria. Return a modified version of the recipe that satisfies all the criteria. Format your response as: '## Original Name' section (the name of the original recipe on one line), then the modified recipe as: recipe name on its own line, then '## Ingredients' section, then '## Instructions' section, then '## Changes' section. The Changes section should be a concise bulleted list of every specific change you made and why (e.g., '- Replaced butter with coconut oil (dairy-free)', '- Reduced sugar by half (less sweet preference)'). Keep the same general structure as the original recipe.",
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude API error: {e}")
        return None


def split_recipe_text(text):
    """Split raw recipe text into ingredients and instructions by looking for common section headers."""
    text_lower = text.lower()

    # Try to find an instructions/directions/steps section
    split_keywords = ["instructions", "directions", "steps", "method", "preparation", "how to"]
    best_pos = -1
    for keyword in split_keywords:
        pos = text_lower.find(keyword)
        if pos != -1 and (best_pos == -1 or pos < best_pos):
            best_pos = pos

    if best_pos != -1:
        # Walk back to the start of the line containing the keyword
        line_start = text.rfind("\n", 0, best_pos)
        line_start = 0 if line_start == -1 else line_start + 1
        ingredients = text[:line_start].strip()
        instructions = text[line_start:].strip()
    else:
        # No clear split found — check if there are numbered lines (likely instructions at the end)
        lines = text.strip().split("\n")
        split_idx = len(lines)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and (stripped[0].isdigit() and (stripped[1:2] == "." or stripped[1:2] == ")")):
                split_idx = i
                break

        if split_idx < len(lines):
            ingredients = "\n".join(lines[:split_idx]).strip()
            instructions = "\n".join(lines[split_idx:]).strip()
        else:
            ingredients = text
            instructions = ""

    return ingredients, instructions


def parse_ai_recipe(ai_text):
    """Parse Claude's response into original name, modified name, ingredients, instructions, and change summary."""
    lines = ai_text.strip().split("\n")

    original_name = ""
    recipe_name = ""
    ingredients = ""
    instructions = ""
    change_summary = ""
    current_section = None

    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## original name"):
            current_section = "original_name"
            continue
        elif stripped.lower().startswith("## ingredients"):
            current_section = "ingredients"
            continue
        elif stripped.lower().startswith("## instructions"):
            current_section = "instructions"
            continue
        elif stripped.lower().startswith("## changes"):
            current_section = "changes"
            continue

        if current_section == "original_name":
            if stripped:
                original_name = stripped.strip("#").strip()
                current_section = "modified_name"
            continue
        elif current_section == "modified_name":
            if stripped and not stripped.startswith("##"):
                recipe_name = stripped.strip("#").strip()
                current_section = None
            continue
        elif current_section == "ingredients":
            ingredients += line + "\n"
        elif current_section == "instructions":
            instructions += line + "\n"
        elif current_section == "changes":
            change_summary += line + "\n"

    # Fallback: if no original name found, use modified name
    if not original_name:
        original_name = recipe_name
    if not recipe_name:
        recipe_name = lines[0].strip().strip("#").strip() if lines else "Modified Recipe"

    return original_name, recipe_name, ingredients.strip(), instructions.strip(), change_summary.strip()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/history")
def history():
    modifications = []
    if supabase:
        result = supabase.table("modifications").select("*, recipes!modifications_original_recipe_id_fkey(recipe_name)").order("created_at", desc=True).execute()
        for row in (result.data or []):
            recipe_info = row.get("recipes", {}) or {}
            modifications.append({
                "id": row["id"],
                "recipe_name": recipe_info.get("recipe_name", "Untitled Recipe"),
                "created_at": row.get("created_at", ""),
                "allergies": row.get("allergies", ""),
                "taste_preferences": row.get("taste_preferences", ""),
                "ingredient_limitations": row.get("ingredient_limitations", ""),
                "equipment_limitations": row.get("equipment_limitations", ""),
                "source_type": row.get("source_type", ""),
            })
    return render_template("history.html", modifications=modifications)


@app.route("/modify")
def modify():
    return render_template("modify.html")


@app.route("/submit", methods=["POST"])
def submit():
    # Collect all possible inputs — user may use any combination
    recipe_title = request.form.get("recipe_title", "").strip()
    recipe_ingredients = request.form.get("recipe_ingredients", "").strip()
    recipe_instructions = request.form.get("recipe_instructions", "").strip()
    pasted_text = request.form.get("recipe_text", "").strip()
    recipe_url = request.form.get("recipe_url", "").strip()
    fetched_content = request.form.get("fetched_recipe_content", "").strip()

    # Read uploaded file (txt / pdf / image) into text if present
    file_text = ""
    file_note = ""
    recipe_file = request.files.get("recipe_file")
    if recipe_file and recipe_file.filename:
        fname = recipe_file.filename
        if fname.lower().endswith(".txt"):
            file_text = recipe_file.read().decode("utf-8", errors="replace")
        elif fname.lower().endswith(".pdf"):
            try:
                reader = PdfReader(io.BytesIO(recipe_file.read()))
                pages = [page.extract_text() or "" for page in reader.pages]
                file_text = "\n".join(pages).strip()
            except Exception as e:
                print(f"PDF extraction error: {e}")
                file_note = f"[Could not extract text from PDF: {fname}]"
        else:
            file_note = f"[Uploaded image: {fname}]"

    # Figure out the recipe name, structured fields, and full text.
    # Priority for name: typed title > fetched URL first line > pasted first line > file > URL > default.
    has_structured = bool(recipe_title or recipe_ingredients or recipe_instructions)

    if has_structured:
        recipe_name = recipe_title or "Untitled Recipe"
        ingredients = recipe_ingredients
        instructions = recipe_instructions
        recipe_text = f"{recipe_name}\n\nIngredients:\n{ingredients}\n\nInstructions:\n{instructions}"
        # Append any additional supporting content the user provided
        extras = []
        if fetched_content:
            extras.append(f"Additional context from URL:\n{fetched_content}")
        elif recipe_url:
            extras.append(f"Reference URL: {recipe_url}")
        if pasted_text:
            extras.append(f"Additional pasted text:\n{pasted_text}")
        if file_text:
            extras.append(f"Additional text from uploaded file:\n{file_text}")
        elif file_note:
            extras.append(file_note)
        if extras:
            recipe_text += "\n\n" + "\n\n".join(extras)
    else:
        # Pick the first non-structured source that has content
        if fetched_content:
            raw = fetched_content
            default_name = "Recipe from URL"
        elif pasted_text:
            raw = pasted_text
            default_name = "Pasted Recipe"
        elif file_text:
            raw = file_text
            default_name = "Uploaded Recipe"
        elif recipe_url:
            raw = f"[Recipe from URL: {recipe_url}]"
            default_name = "Recipe from URL"
        elif file_note:
            raw = file_note
            default_name = "Uploaded Recipe"
        else:
            raw = ""
            default_name = "Created Recipe"

        recipe_text = raw
        first_line = raw.split("\n", 1)[0].strip() if raw else ""
        recipe_name = first_line if first_line and not first_line.startswith("[") else default_name
        ingredients, instructions = split_recipe_text(raw) if raw else ("", "")

    # Source type for history display
    if has_structured:
        mode = "create"
    elif fetched_content or recipe_url:
        mode = "url"
    elif file_text or file_note:
        mode = "upload"
    elif pasted_text:
        mode = "paste"
    else:
        mode = "create"

    # Collect criteria
    allergies_list = request.form.getlist("allergies")
    allergies_other = request.form.get("allergies_other", "").strip()
    if allergies_other:
        allergies_list.append(allergies_other)
    allergies = ", ".join(allergies_list)

    taste_list = request.form.getlist("taste")
    taste_other = request.form.get("taste_other", "").strip()
    if taste_other:
        taste_list.append(taste_other)
    taste_preferences = ", ".join(taste_list)

    ingredient_limitations = request.form.get("ingredient_limitations", "").strip()

    equipment_list = request.form.getlist("equipment")
    equipment_other = request.form.get("equipment_other", "").strip()
    if equipment_other:
        equipment_list.append(equipment_other)
    equipment_limitations = ", ".join(equipment_list)

    scaling = request.form.get("scaling", "1").strip()

    # Call Claude API to generate modified recipe
    ai_result = modify_recipe_with_ai(recipe_text, allergies, taste_preferences, ingredient_limitations, equipment_limitations, scaling)
    change_summary = ""

    if ai_result:
        ai_original_name, mod_name, mod_ingredients, mod_instructions, change_summary = parse_ai_recipe(ai_result)
        # For upload mode, use Claude's extracted name for the original recipe
        if not has_structured and ai_original_name:
            recipe_name = ai_original_name
    else:
        mod_name = f"Modified {recipe_name}"
        mod_ingredients = f"[AI unavailable — placeholder]\n\nOriginal:\n{ingredients}"
        mod_instructions = "[AI unavailable — placeholder]"

    if supabase:
        # Save original recipe
        original = supabase.table("recipes").insert({
            "recipe_name": recipe_name,
            "ingredients": ingredients,
            "instructions": instructions,
            "is_original": True,
        }).execute()
        original_id = original.data[0]["id"]

        # Save AI-generated modified recipe
        modified = supabase.table("recipes").insert({
            "recipe_name": mod_name,
            "ingredients": mod_ingredients,
            "instructions": mod_instructions,
            "is_original": False,
            "original_recipe_id": original_id,
        }).execute()
        modified_id = modified.data[0]["id"]

        # Save modification record
        mod_record = supabase.table("modifications").insert({
            "original_recipe_id": original_id,
            "modified_recipe_id": modified_id,
            "allergies": allergies,
            "taste_preferences": taste_preferences,
            "ingredient_limitations": ingredient_limitations,
            "equipment_limitations": equipment_limitations,
            "change_summary": change_summary,
            "source_type": mode,
        }).execute()
        modification_id = mod_record.data[0]["id"]

        return redirect(url_for("results", modification_id=modification_id))
    else:
        # No Supabase — use placeholder ID for demo
        return redirect(url_for("results", modification_id="demo"))


@app.route("/results/<modification_id>")
def results(modification_id):
    if supabase and modification_id != "demo":
        # Fetch modification record
        mod = supabase.table("modifications").select("*").eq("id", modification_id).execute()
        modification = mod.data[0] if mod.data else {}

        # Fetch original recipe
        orig = supabase.table("recipes").select("*").eq("id", modification.get("original_recipe_id")).execute()
        original_recipe = orig.data[0] if orig.data else {}

        # Fetch modified recipe
        modr = supabase.table("recipes").select("*").eq("id", modification.get("modified_recipe_id")).execute()
        modified_recipe = modr.data[0] if modr.data else {}

        # Fetch chat messages
        chat = supabase.table("chat_messages").select("*").eq("modification_id", modification_id).order("created_at").execute()
        chat_messages = chat.data if chat.data else []
    else:
        # Demo/placeholder data when Supabase is not connected
        modification = {
            "id": "demo",
            "allergies": "nut-free, dairy-free",
            "taste_preferences": "less sweet",
            "ingredient_limitations": "No coconut",
            "equipment_limitations": "no stand mixer",
        }
        original_recipe = {
            "recipe_name": "Classic Chocolate Chip Cookies",
            "ingredients": "2 1/4 cups flour\n1 cup butter\n3/4 cup sugar\n2 eggs\n1 tsp vanilla\n2 cups chocolate chips",
            "instructions": "1. Preheat oven to 375F\n2. Mix dry ingredients\n3. Cream butter and sugar\n4. Add eggs and vanilla\n5. Combine wet and dry\n6. Fold in chocolate chips\n7. Bake 9-11 minutes",
        }
        modified_recipe = {
            "recipe_name": "Modified Classic Chocolate Chip Cookies",
            "ingredients": "[Demo mode — submit a recipe to see AI modifications]",
            "instructions": "[Demo mode — submit a recipe to see AI modifications]",
        }
        chat_messages = []

    return render_template("results.html",
        modification=modification,
        original_recipe=original_recipe,
        modified_recipe=modified_recipe,
        chat_messages=chat_messages,
    )


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    modification_id = data.get("modification_id", "")
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "No message provided."}), 400

    # Load recipe context for the system prompt
    original_recipe = {}
    modified_recipe = {}
    modification = {}
    history = []

    if supabase and modification_id != "demo":
        mod = supabase.table("modifications").select("*").eq("id", modification_id).execute()
        modification = mod.data[0] if mod.data else {}

        if modification:
            orig = supabase.table("recipes").select("*").eq("id", modification.get("original_recipe_id")).execute()
            original_recipe = orig.data[0] if orig.data else {}

            modr = supabase.table("recipes").select("*").eq("id", modification.get("modified_recipe_id")).execute()
            modified_recipe = modr.data[0] if modr.data else {}

        # Load conversation history
        chat_rows = supabase.table("chat_messages").select("*").eq("modification_id", modification_id).order("created_at").execute()
        history = chat_rows.data if chat_rows.data else []

    # Build system prompt with recipe context
    system_prompt = """You are a helpful baking assistant. The user is looking at a modified recipe. Help them with follow-up questions — they might ask for further tweaks, substitution ideas, baking tips, or explanations of why a change was made. Keep responses concise and friendly.

IMPORTANT: You must ALWAYS respond with valid JSON in one of these two formats:

1. When the user asks for substitutions, alternatives, or options (e.g. "what can I use instead of X", "give me options for Y", "substitute for Z"):
{"type": "choices", "question": "Short question summarizing what you're offering", "options": [{"label": "Option name", "description": "Brief explanation of this option"}, ...]}
Provide 2-4 options. Keep labels short (1-3 words) and descriptions to one sentence.

2. For all other messages (questions, tips, explanations, general chat):
{"type": "message", "content": "Your response text here"}

Always respond with ONLY the JSON object, no other text."""

    if original_recipe or modified_recipe or modification:
        context_parts = []
        if original_recipe:
            context_parts.append(f"Original Recipe: {original_recipe.get('recipe_name', '')}\nIngredients:\n{original_recipe.get('ingredients', '')}\nInstructions:\n{original_recipe.get('instructions', '')}")
        if modified_recipe:
            context_parts.append(f"Modified Recipe: {modified_recipe.get('recipe_name', '')}\nIngredients:\n{modified_recipe.get('ingredients', '')}\nInstructions:\n{modified_recipe.get('instructions', '')}")
        if modification:
            criteria = []
            if modification.get("allergies"):
                criteria.append(f"Allergies: {modification['allergies']}")
            if modification.get("taste_preferences"):
                criteria.append(f"Taste: {modification['taste_preferences']}")
            if modification.get("ingredient_limitations"):
                criteria.append(f"Ingredient limitations: {modification['ingredient_limitations']}")
            if modification.get("equipment_limitations"):
                criteria.append(f"Equipment limitations: {modification['equipment_limitations']}")
            if criteria:
                context_parts.append("Modification criteria:\n" + "\n".join(criteria))
        system_prompt += "\n\nHere is the context:\n\n" + "\n\n".join(context_parts)

    # Build messages array with conversation history
    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    # Call Claude API
    reply = '{"type": "message", "content": "Sorry, I couldn\'t process your message right now. Please try again."}'
    if claude:
        try:
            response = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                system=system_prompt,
                messages=messages,
            )
            reply = response.content[0].text
        except Exception as e:
            print(f"Claude chat API error: {e}")
            reply = '{"type": "message", "content": "Sorry, something went wrong. Please try again."}'

    # Save messages to Supabase
    if supabase and modification_id != "demo":
        supabase.table("chat_messages").insert({
            "modification_id": modification_id,
            "role": "user",
            "content": message,
        }).execute()

        supabase.table("chat_messages").insert({
            "modification_id": modification_id,
            "role": "assistant",
            "content": reply,
        }).execute()

    # Parse the JSON reply for the frontend
    try:
        parsed = extract_json(reply)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = {"type": "message", "content": reply}

    return jsonify(parsed)


@app.route("/api/chat/apply", methods=["POST"])
def chat_apply():
    data = request.get_json()
    modification_id = data.get("modification_id", "")
    choice_label = data.get("choice_label", "").strip()
    question = data.get("question", "").strip()

    if not choice_label or not modification_id:
        return jsonify({"error": "Missing data."}), 400

    if not supabase or not claude:
        return jsonify({"error": "Service unavailable."}), 503

    # Load current modified recipe and context
    mod = supabase.table("modifications").select("*").eq("id", modification_id).execute()
    modification = mod.data[0] if mod.data else {}
    if not modification:
        return jsonify({"error": "Modification not found."}), 404

    modr = supabase.table("recipes").select("*").eq("id", modification.get("modified_recipe_id")).execute()
    modified_recipe = modr.data[0] if modr.data else {}

    # Ask Claude to apply the choice to the recipe
    apply_prompt = f"""Here is the current modified recipe:

Name: {modified_recipe.get('recipe_name', '')}

Ingredients:
{modified_recipe.get('ingredients', '')}

Instructions:
{modified_recipe.get('instructions', '')}

The user was asked: "{question}"
They chose: "{choice_label}"

Apply this choice to the recipe. Return ONLY valid JSON in this format:
{{"ingredients": "updated full ingredients list", "instructions": "updated full instructions list", "change_description": "short description of what changed, e.g. Substituted butter → coconut oil"}}

Keep everything else in the recipe the same. Only modify what is necessary to apply the chosen option."""

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system="You are a recipe modification assistant. Apply the user's chosen substitution to the recipe. Return only valid JSON with the updated recipe sections.",
            messages=[{"role": "user", "content": apply_prompt}],
        )
        raw_text = response.content[0].text
        result = extract_json(raw_text)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"Failed to parse apply response: {e}\nRaw: {raw_text if 'raw_text' in dir() else 'N/A'}")
        return jsonify({"error": "Failed to parse AI response."}), 500
    except Exception as e:
        print(f"Claude apply API error: {e}")
        return jsonify({"error": "AI request failed."}), 500

    new_ingredients = result.get("ingredients", modified_recipe.get("ingredients", ""))
    new_instructions = result.get("instructions", modified_recipe.get("instructions", ""))
    change_desc = result.get("change_description", f"Applied: {choice_label}")

    # Update the modified recipe in Supabase
    supabase.table("recipes").update({
        "ingredients": new_ingredients,
        "instructions": new_instructions,
    }).eq("id", modification.get("modified_recipe_id")).execute()

    # Append to chat_modifications log
    existing_log = modification.get("chat_modifications", "") or ""
    new_log = (existing_log + "\n" + change_desc).strip() if existing_log else change_desc
    supabase.table("modifications").update({
        "chat_modifications": new_log,
    }).eq("id", modification_id).execute()

    # Save the choice as a chat message pair
    supabase.table("chat_messages").insert({
        "modification_id": modification_id,
        "role": "user",
        "content": f"Apply: {choice_label}",
    }).execute()
    supabase.table("chat_messages").insert({
        "modification_id": modification_id,
        "role": "assistant",
        "content": json.dumps({"type": "message", "content": f"Done! I've updated the recipe: {change_desc}"}),
    }).execute()

    return jsonify({
        "ingredients": new_ingredients,
        "instructions": new_instructions,
        "change_description": change_desc,
    })


@app.route("/api/fetch-url", methods=["POST"])
def fetch_url():
    data = request.get_json()
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "No URL provided."}), 400

    # Fetch the page content
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (compatible; BakeShift/1.0)"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        page_text = soup.get_text(separator="\n", strip=True)
        # Trim to a reasonable size for Claude
        page_text = page_text[:8000]
    except Exception as e:
        print(f"URL fetch error: {e}")
        return jsonify({"content": f"Could not fetch the page. Please check the URL and try again."})

    # Send to Claude to extract the recipe
    if claude:
        try:
            response = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system="You are a recipe extraction assistant. The user has fetched a webpage. Extract the recipe from the page text and return it in a clean format: recipe name on the first line, then 'Ingredients:' section, then 'Instructions:' section. If there is no recipe on the page, say so briefly.",
                messages=[{"role": "user", "content": f"Extract the recipe from this page:\n\n{page_text}"}],
            )
            return jsonify({"content": response.content[0].text})
        except Exception as e:
            print(f"Claude API error in fetch_url: {e}")

    # Fallback: return raw extracted text
    return jsonify({"content": page_text[:3000]})


if __name__ == "__main__":
    app.run(debug=True)
