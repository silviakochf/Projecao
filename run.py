from app import create_app

# Cria a aplicação usando a fábrica que está lá dentro da pasta app
app = create_app()

if __name__ == "__main__":
    # Roda o servidor acessível na rede (0.0.0.0)
    app.run(debug=True, host='0.0.0.0', port=5000)