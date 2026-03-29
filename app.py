import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
from supabase import create_client
import anthropic

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


def modify_recipe_with_ai(recipe_text, allergies, taste_preferences, ingredient_limitations, equipment_limitations):
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

    criteria_text = "\n".join(criteria_parts) if criteria_parts else "No specific criteria provided."

    user_message = f"""Here is the original recipe:

{recipe_text}

Please modify this recipe based on the following criteria:
{criteria_text}"""

    try:
        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system="You are a professional baker and recipe developer. The user will give you a recipe and modification criteria. Return a modified version of the recipe that satisfies all the criteria. Format your response as: recipe name on the first line, then '## Ingredients' section, then '## Instructions' section. Keep the same general structure as the original recipe.",
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
    """Parse Claude's response into recipe name, ingredients, and instructions."""
    lines = ai_text.strip().split("\n")

    recipe_name = lines[0].strip().strip("#").strip()

    ingredients = ""
    instructions = ""
    current_section = None

    for line in lines[1:]:
        stripped = line.strip()
        if stripped.lower().startswith("## ingredients"):
            current_section = "ingredients"
            continue
        elif stripped.lower().startswith("## instructions"):
            current_section = "instructions"
            continue

        if current_section == "ingredients":
            ingredients += line + "\n"
        elif current_section == "instructions":
            instructions += line + "\n"

    return recipe_name, ingredients.strip(), instructions.strip()


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/modify")
def modify():
    mode = request.args.get("mode", "upload")
    return render_template("modify.html", mode=mode)


@app.route("/submit", methods=["POST"])
def submit():
    mode = request.form.get("mode", "upload")

    # Collect recipe content based on mode
    if mode == "upload":
        recipe_text = request.form.get("recipe_text", "").strip()
        # If a file was uploaded, read its text content
        recipe_file = request.files.get("recipe_file")
        if recipe_file and recipe_file.filename:
            if recipe_file.filename.endswith(".txt"):
                recipe_text = recipe_file.read().decode("utf-8", errors="replace")
            else:
                recipe_text = recipe_text or f"[Uploaded image: {recipe_file.filename}]"
        recipe_name = "Uploaded Recipe"
    else:
        typed = request.form.get("typed_recipe", "").strip()
        recipe_url = request.form.get("recipe_url", "").strip()
        recipe_text = typed or (f"[Recipe from URL: {recipe_url}]" if recipe_url else "")
        recipe_name = "Created Recipe"

    # Split raw recipe text into ingredients and instructions
    ingredients, instructions = split_recipe_text(recipe_text)

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

    # Call Claude API to generate modified recipe
    ai_result = modify_recipe_with_ai(recipe_text, allergies, taste_preferences, ingredient_limitations, equipment_limitations)

    if ai_result:
        mod_name, mod_ingredients, mod_instructions = parse_ai_recipe(ai_result)
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
    system_prompt = "You are a helpful baking assistant. The user is looking at a modified recipe. Help them with follow-up questions — they might ask for further tweaks, substitution ideas, baking tips, or explanations of why a change was made. Keep responses concise and friendly."

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
    reply = "Sorry, I couldn't process your message right now. Please try again."
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
            reply = "Sorry, something went wrong. Please try again."

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

    return jsonify({"reply": reply})


@app.route("/api/fetch-url", methods=["POST"])
def fetch_url():
    data = request.get_json()
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "No URL provided."}), 400

    if claude:
        try:
            response = claude.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                system="The user has pasted a recipe URL. We cannot fetch the URL content yet. Acknowledge the URL and let them know the recipe will need to be typed or pasted manually for now. Be brief and friendly.",
                messages=[{"role": "user", "content": f"I pasted this recipe URL: {url}"}],
            )
            return jsonify({"content": response.content[0].text})
        except Exception as e:
            print(f"Claude API error in fetch_url: {e}")

    return jsonify({"content": f"URL fetching is not available yet. Please copy and paste the recipe text from {url} into the 'Type It In' box above."})


if __name__ == "__main__":
    app.run(debug=True)
