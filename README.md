# Mira Food-Ordering Chatbot

A food-ordering chatbot prototype built with Dialogflow ES, FastAPI, Python, SQLAlchemy, HTML, CSS, and JavaScript.

Users can start an order, add or remove food items, confirm the order, receive an order ID and total, and track the saved order's status.

The GitHub project is named Mira. Its connected Dialogflow agent is named Ira-Chatbot.

## Features

- Natural-language ordering through Dialogflow ES.
- Food names, quantities, and order IDs extracted as parameters.
- Session-based carts stored in a database.
- Adding and removing menu items.
- Atomic checkout with database-generated order IDs.
- Order totals calculated from stored menu prices.
- Order-status lookup.
- A local browser interface for demonstrating the ordering service.
- A token-protected webhook gateway for the Dialogflow connection.

## Architecture

Dialogflow conversation:

User → Dialogflow ES → HTTPS tunnel → Webhook gateway → FastAPI → Database

Local browser demonstration:

Browser → FastAPI → Database

Dialogflow performs intent classification and parameter extraction. The Python backend validates the request and executes the corresponding database operation.

The local browser interface uses menu controls rather than natural-language classification.

## Technology Stack

- Python 3.12+
- FastAPI and Uvicorn
- Dialogflow ES
- SQLAlchemy
- SQLite by default
- Optional MySQL support through PyMySQL
- HTML, CSS, and JavaScript
- Cloudflare Tunnel for temporary HTTPS access during development

## Run Locally on macOS

Clone the repository:

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/bansaldhruv20/Chatbot_Mira.git
cd Chatbot_Mira
```

Install dependencies:

```bash
bash scripts/setup.sh
```

Start the application:

```bash
bash scripts/run.sh
```

Open this address in your browser:

```text
http://127.0.0.1:8000
```

Keep the Terminal window running.

The application automatically creates the local SQLite database and seeds the menu on first startup.

## Local Browser Demonstration

1. Add two pizzas.
2. Add one mango lassi.
3. Remove the mango lassi.
4. Confirm the order.
5. Note the returned order ID and total of 16.00.
6. Track that order ID.

Prices retain the original project's demo values; no specific currency is implied.

## Connect Dialogflow

### 1. Prepare the agent

Restore the corrected Dialogflow ES agent ZIP after exporting a backup of the existing agent.

The corrected agent uses these intents:

- `new.order`
- `order.add - context: ongoing-order`
- `order.remove - context: ongoing-order`
- `order.complete - context: ongoing-order`
- `track.order`
- `track.order - context: ongoing-tracking`

The ordering context is `on-going`.
The tracking context is `on-goingtracking`.

### 2. Start the webhook gateway

Keep the application running in the first Terminal tab.

Open a second tab:

```bash
cd ~/Projects/Chatbot_Mira
```

Generate a private token:

```bash
export WEBHOOK_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Copy the token to the Mac clipboard:

```bash
printf '%s' "$WEBHOOK_TOKEN" | pbcopy
```

Start the gateway:

```bash
python3 scripts/webhook_proxy.py
```

The gateway listens on local port 8082. It forwards only authenticated POST requests to `/webhook`; the local website and other API routes are not forwarded.

### 3. Start the HTTPS tunnel

Install Cloudflare Tunnel if needed:

```bash
brew install cloudflared
```

Open a third Terminal tab:

```bash
cloudflared tunnel --url http://127.0.0.1:8082
```

Cloudflare prints a temporary HTTPS address.

### 4. Configure Dialogflow Fulfillment

In Dialogflow ES, open **Fulfillment** and enable the webhook.

Set the URL to the tunnel address followed by `/webhook`:

```text
https://YOUR-TUNNEL.trycloudflare.com/webhook
```

Add this header:

| Header | Value |
|---|---|
| `X-Webhook-Token` | The private token generated in the gateway Terminal tab |

Save the configuration.

Do not put the token in the webhook URL or commit it to GitHub.

The temporary tunnel address changes when the tunnel restarts. Update the Dialogflow Fulfillment URL whenever it changes.

## Verified Conversation

The following complete conversation was manually verified through Dialogflow:

1. `new order`
2. `I want two pizzas and one mango lassi`
3. `remove mango lassi`
4. `done`
5. `track order`
6. Enter the order ID returned at checkout.

Checkout returned a saved order ID and total of 16.00. Tracking returned the stored status, `in progress`.

This verifies the integration flow. It does not measure intent-classification accuracy across a labeled evaluation dataset.

## Database

SQLite is the default database. Data is stored in `mira.db`, which is excluded from Git.

The application uses these tables:

- `mira_food`
- `mira_cart`
- `mira_order`
- `mira_order_item`
- `mira_interaction`

Carts and orders persist across application restarts as long as the database file is retained.

The original `database/pandeyji_eatery.sql` is preserved as the historical MySQL schema and sample data. It is not required for the default SQLite setup, and its historical orders are not automatically migrated.

For optional MySQL use, create a dedicated database and supply `DATABASE_URL` before starting the application:

```text
mysql+pymysql://USER:URL_ENCODED_PASSWORD@HOST:3306/DATABASE
```

Keep actual credentials outside the repository.

## Important Files

```text
backend/
  __init__.py
  main.py
  dp_helper.py
  generic_helper.py

frontend/
  home.html
  styles.css
  app.js

scripts/
  setup.sh
  run.sh
  webhook_proxy.py

requirements.txt
.gitignore
```
