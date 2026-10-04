from app import create_app

app = create_app()

if __name__ == "__main__":
    # Avoid macOS AirPlay Receiver, which binds :5000 and returns HTTP 403.
    app.run(debug=True, port=5001)
