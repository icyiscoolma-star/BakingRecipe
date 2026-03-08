document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("modify-form");
  const mode = form.querySelector('input[name="mode"]').value;

  // File upload preview — upload mode
  const fileUpload = document.getElementById("file-upload");
  if (fileUpload) {
    fileUpload.addEventListener("change", function () {
      const preview = document.getElementById("upload-preview");
      const file = this.files[0];
      if (!file) {
        preview.classList.remove("active");
        preview.innerHTML = "";
        return;
      }
      preview.classList.add("active");
      if (file.type.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = URL.createObjectURL(file);
        preview.innerHTML = "";
        preview.appendChild(img);
      } else {
        const reader = new FileReader();
        reader.onload = function (e) {
          preview.textContent = e.target.result;
        };
        reader.readAsText(file);
      }
    });
  }

  // Photo upload preview — create mode
  const photoUpload = document.getElementById("photo-upload");
  if (photoUpload) {
    photoUpload.addEventListener("change", function () {
      const preview = document.getElementById("photo-preview");
      const file = this.files[0];
      if (!file) {
        preview.classList.remove("active");
        preview.innerHTML = "";
        return;
      }
      preview.classList.add("active");
      const img = document.createElement("img");
      img.src = URL.createObjectURL(file);
      preview.innerHTML = "";
      preview.appendChild(img);
    });
  }

  // URL fetch — create mode
  const fetchBtn = document.getElementById("fetch-url-btn");
  if (fetchBtn) {
    fetchBtn.addEventListener("click", function () {
      const urlInput = document.getElementById("recipe-url");
      const preview = document.getElementById("url-preview");
      const url = urlInput.value.trim();
      if (!url) {
        alert("Please enter a URL first.");
        return;
      }
      fetchBtn.disabled = true;
      fetchBtn.textContent = "Fetching...";
      fetch("/api/fetch-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url }),
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          preview.classList.add("active");
          preview.textContent = data.content || data.error;
        })
        .catch(function () {
          preview.classList.add("active");
          preview.textContent = "Failed to fetch URL.";
        })
        .finally(function () {
          fetchBtn.disabled = false;
          fetchBtn.textContent = "Fetch";
        });
    });
  }

  // Form validation
  form.addEventListener("submit", function (e) {
    if (mode === "upload") {
      var text = document.getElementById("recipe-text").value.trim();
      var file = document.getElementById("file-upload").files.length > 0;
      if (!text && !file) {
        e.preventDefault();
        alert("Please paste recipe text or upload a file before submitting.");
      }
    } else {
      var typed = document.getElementById("type-recipe").value.trim();
      var url = document.getElementById("recipe-url").value.trim();
      var photo = document.getElementById("photo-upload").files.length > 0;
      if (!typed && !url && !photo) {
        e.preventDefault();
        alert("Please provide a recipe by typing it in, pasting a URL, or uploading a photo.");
      }
    }
  });
});
