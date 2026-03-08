import os
from flask import Flask, render_template, request, jsonify, redirect, url_for
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

app = Flask(__name__)

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = None
if supabase_url and supabase_key and supabase_url != "your_supabase_url_here":
    supabase = create_client(supabase_url, supabase_key)


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
        ingredients = recipe_text
        instructions = ""
    else:
        typed = request.form.get("typed_recipe", "").strip()
        recipe_url = request.form.get("recipe_url", "").strip()
        recipe_text = typed or (f"[Recipe from URL: {recipe_url}]" if recipe_url else "")
        recipe_name = "Created Recipe"
        ingredients = recipe_text
        instructions = ""

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

    if supabase:
        # Save original recipe
        original = supabase.table("recipes").insert({
            "recipe_name": recipe_name,
            "ingredients": ingredients,
            "instructions": instructions,
            "is_original": True,
        }).execute()
        original_id = original.data[0]["id"]

        # Create placeholder modified recipe
        modified = supabase.table("recipes").insert({
            "recipe_name": f"Modified {recipe_name}",
            "ingredients": f"[AI-modified version of ingredients will appear here]\n\nOriginal:\n{ingredients}",
            "instructions": "[AI-modified instructions will appear here]",
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
            "ingredients": "[AI-modified version will appear here once AI integration is added]\n\nOriginal:\n2 1/4 cups flour\n1 cup butter\n3/4 cup sugar\n2 eggs\n1 tsp vanilla\n2 cups chocolate chips",
            "instructions": "[AI-modified instructions will appear here]",
        }
        chat_messages = []

    return render_template("results.html",
        modification=modification,
        original_recipe=original_recipe,
        modified_recipe=modified_recipe,
        chat_messages=chat_messages,
    )


@app.route("/api/fetch-url", methods=["POST"])
def fetch_url():
    data = request.get_json()
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "No URL provided."}), 400
    # Placeholder — AI extraction will be added later
    return jsonify({"content": f"Recipe content from {url} will be extracted here once AI integration is added."})


if __name__ == "__main__":
    app.run(debug=True)
