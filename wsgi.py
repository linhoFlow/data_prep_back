from app import create_app

print("[WSGI] Starting application creation...", flush=True)
app = create_app()
print("[WSGI] Application created successfully.", flush=True)

if __name__ == "__main__":
    app.run()
