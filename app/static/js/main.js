(() => {
    "use strict";

    function toast(message) {
        const existing = document.querySelector(".toast");
        if (existing) existing.remove();

        const el = document.createElement("div");
        el.className = "toast";
        el.setAttribute("role", "status");
        el.textContent = message;
        document.body.appendChild(el);
        window.setTimeout(() => el.remove(), 2400);
    }

    async function copyText(text, successMessage) {
        try {
            await navigator.clipboard.writeText(text);
            toast(successMessage);
        } catch (error) {
            window.prompt("Copy this link", text);
        }
    }

    document.addEventListener("click", (event) => {
        const like = event.target.closest("[data-like]");
        if (like) {
            const liked = like.getAttribute("aria-pressed") === "true";
            like.setAttribute("aria-pressed", String(!liked));
            like.classList.toggle("liked", !liked);
            const label = like.querySelector(".label");
            if (label) label.textContent = liked ? "Like" : "Liked";
            return;
        }

        const share = event.target.closest("[data-share]");
        if (share) {
            const url = share.dataset.url || window.location.href;
            copyText(url, "Link copied to clipboard");
            return;
        }

        const chip = event.target.closest("[data-amount]");
        if (chip) {
            const field = document.querySelector("#amount");
            if (field) field.value = chip.dataset.amount;
            document.querySelectorAll(".amount-chip").forEach((item) => {
                item.classList.toggle("active", item === chip);
            });
            return;
        }

        const copy = event.target.closest("[data-copy]");
        if (copy) {
            copyText(copy.dataset.copy, "Campaign story copied");
        }
    });

    const amountField = document.querySelector("#amount");
    if (amountField) {
        amountField.addEventListener("input", () => {
            document.querySelectorAll(".amount-chip").forEach((chip) => {
                chip.classList.toggle(
                    "active",
                    chip.dataset.amount === amountField.value
                );
            });
        });
    }
})();
