let session = localStorage.getItem("mira-session");

if (!session) {
    session = crypto.randomUUID();
    localStorage.setItem("mira-session", session);
}

const conversation = document.querySelector("#messages");
const statusMessage = document.querySelector("#status");

let pending = false;


function message(text, speaker = "Mira") {
    const paragraph = document.createElement("p");

    // Use textContent so messages are displayed as text, not HTML.
    paragraph.textContent = `${speaker}: ${text}`;

    conversation.append(paragraph);
    conversation.scrollTop = conversation.scrollHeight;
}


async function act(action, extra = {}) {
    if (pending) {
        return;
    }

    pending = true;

    document.querySelectorAll("button").forEach((button) => {
        button.disabled = true;
    });

    try {
        const response = await fetch("/api/action", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                session,
                action,
                ...extra,
            }),
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                typeof result.detail === "string"
                    ? result.detail
                    : "Please check your input."
            );
        }

        message(result.fulfillmentText);

        if (result.order_id) {
            document.querySelector("#order-id").value =
                result.order_id;
        }

        statusMessage.textContent = "";

    } catch (error) {
        statusMessage.textContent = error.message;

    } finally {
        pending = false;

        document.querySelectorAll("button").forEach((button) => {
            button.disabled = false;
        });
    }
}


async function loadMenu() {
    try {
        const response = await fetch("/api/menu");

        if (!response.ok) {
            throw new Error(
                "Menu unavailable. Please reload after checking the server."
            );
        }

        const foods = await response.json();

        for (const food of foods) {
            const card = document.createElement("article");

            const title = document.createElement("h3");
            title.textContent = food.name;

            const price = document.createElement("p");
            price.textContent = `Price: ${food.price}`;

            const count = document.createElement("input");
            count.type = "number";
            count.min = "1";
            count.max = "99";
            count.step = "1";
            count.value = "1";

            count.setAttribute(
                "aria-label",
                `${food.name} quantity`
            );

            const add = document.createElement("button");
            add.type = "button";
            add.textContent = "Add";

            add.onclick = () => {
                if (!count.checkValidity()) {
                    count.reportValidity();
                    return;
                }

                message(
                    `Add ${count.value} ${food.name}`,
                    "You"
                );

                act("add", {
                    items: [food.name],
                    quantities: [Number(count.value)],
                });
            };

            const remove = document.createElement("button");
            remove.type = "button";
            remove.textContent = "Remove";

            remove.onclick = () => {
                act("remove", {
                    items: [food.name],
                });
            };

            card.append(
                title,
                price,
                count,
                add,
                remove
            );

            document.querySelector("#menu").append(card);
        }

        message(
            "Welcome! Choose food and quantities from the menu, " +
            "then confirm your order."
        );

        await act("cart");

    } catch (error) {
        statusMessage.textContent = error.message;
    }
}


document.querySelector("#cart").onclick = () => {
    act("cart");
};

document.querySelector("#confirm").onclick = () => {
    act("complete");
};

document.querySelector("#new").onclick = () => {
    act("new");
};

document.querySelector("#tracking").onsubmit = (event) => {
    event.preventDefault();

    act("track", {
        order_id: document.querySelector("#order-id").value,
    });
};


loadMenu();
