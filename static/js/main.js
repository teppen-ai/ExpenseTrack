// Mobile navigation: hamburger button toggles the slide-in sidebar.
(function () {
    var toggle = document.getElementById("nav-toggle");
    var links = document.getElementById("nav-links");
    var backdrop = document.getElementById("nav-backdrop");
    if (!toggle || !links || !backdrop) {
        return;
    }

    function setOpen(open) {
        links.classList.toggle("is-open", open);
        backdrop.hidden = !open;
        document.body.classList.toggle("nav-open", open);
        toggle.setAttribute("aria-expanded", open ? "true" : "false");
        toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    }

    toggle.addEventListener("click", function () {
        setOpen(!links.classList.contains("is-open"));
    });
    backdrop.addEventListener("click", function () {
        setOpen(false);
    });
    links.addEventListener("click", function (event) {
        if (event.target.closest("a")) {
            setOpen(false);
        }
    });
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            setOpen(false);
        }
    });
    // Reset if the window grows past the mobile breakpoint while open.
    window.matchMedia("(min-width: 701px)").addEventListener("change", function (event) {
        if (event.matches) {
            setOpen(false);
        }
    });
})();
