from app import create_app
from config import NGROK_TOKEN, NGROK_DOMAIN

app = create_app()

if __name__ == "__main__":
    if NGROK_TOKEN:
        from pyngrok import ngrok
        ngrok.set_auth_token(NGROK_TOKEN)
        tunnel = ngrok.connect("5000", domain=NGROK_DOMAIN or None)
        print(f"Ngrok URL: {tunnel.public_url}")
    app.run(debug=False, port=5000)
