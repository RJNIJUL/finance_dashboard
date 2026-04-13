// ================= DARK MODE TOGGLE =================
function toggleTheme() {
    document.body.classList.toggle("dark-mode");

    const isDark = document.body.classList.contains("dark-mode");

    // Save preference
    localStorage.setItem("theme", isDark ? "dark" : "light");

    // Update icon safely
    const icon = document.getElementById("themeIcon");
    if (icon) {
        icon.innerText = isDark ? "☀️" : "🌙";
    }
}

// ================= LOAD SAVED THEME =================
window.addEventListener("DOMContentLoaded", function () {
    const savedTheme = localStorage.getItem("theme");

    if (savedTheme === "dark") {
        document.body.classList.add("dark-mode");
    }

    const icon = document.getElementById("themeIcon");
    if (icon) {
        icon.innerText = savedTheme === "dark" ? "☀️" : "🌙";
    }
});