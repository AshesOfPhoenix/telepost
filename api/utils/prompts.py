SUCCESS_PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Connection Successful</title>
    <style>
        body {{
            font-family: -apple-system, system-ui, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: #f0f2f5;
        }}
        .container {{
            text-align: center;
            padding: 2rem;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 400px;
            width: 90%;
        }}
        .success-icon {{
            color: #4CAF50;
            font-size: 48px;
            margin-bottom: 1rem;
        }}
        .message {{
            margin: 1rem 0;
            color: #1a1a1a;
        }}
        .telegram-link {{
            display: inline-block;
            margin-top: 1rem;
            color: #0088cc;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success-icon">✓</div>
        <h2>Successfully Connected!</h2>
        <p class="message">Your Threads account has been connected successfully.</p>
        <a href="{redirect_url}" class="telegram-link">
            Return to Telegram
        </a>
    </div>
    <script>
        setTimeout(() => {{
            window.close();
            window.location.href = "{redirect_url}";
        }}, 3000);
    </script>
</body>
</html>
"""