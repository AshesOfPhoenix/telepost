HELP_MESSAGE = """
🤖 *Welcome to the Help Center!*

Here are all the commands you can use:

📝 *Content Creation*
• /post - Create and share a new post
• /thread - Create a thread of connected posts
• /schedule - Schedule posts for later

📊 *Management*
• /account - View your connected accounts
• /status - Check your scheduled posts
• /cancel - Cancel a scheduled post

🔗 *Account Settings*
• /connect - Link your social media accounts
• /disconnect - Remove linked accounts
• /settings - Adjust your preferences

💡 *Need more help?*
Feel free to ask me anything! I'm here to assist you 24/7.
"""

START_MESSAGE = """
✨ *Welcome to Telepost Bot!* ✨

Your all-in-one solution for social media management:
• 📱 Manage multiple platforms
• 📊 Schedule your content
• 🧵 Create engaging threads
• ✍️ Improve your posts

🚀 *Let's get started!*
Use /connect to link your social media accounts.
Use /help to see all available commands.
"""

CONNECT_MESSAGE = """
🔗 *Connect Your Social Media*

Choose a platform to connect:
• Threads - Share your thoughts
• Twitter - Reach your audience

👇 *Click the buttons below to begin*
"""

RESTART_MESSAGE = """
🔄 *Bot Restarted Successfully*

All systems are back online! You can continue using all commands.
Use /help to see available options.
"""

ACCOUNT_INFO_MESSAGE = """
✨ *Threads Account Information* ✨

👤 *Profile Information*
• Username: *@{username}*
• Profile: [Open on Threads](https://www.threads.net/@{username})

📝 *Bio*
{bio}

⚡️ *Quick Actions*
• 📝 /post - Share new content
• 📅 /schedule - Plan future posts
• ⚙️ /settings - Manage account
• ❌ /disconnect - Remove account

💡 *Tip:* Use /help to see all available commands
"""

DISCONNECTED_MESSAGE = """
❌ *Account Disconnected*

Your account has been successfully unlinked.
Use /connect to add it back anytime!
"""

ERROR_MESSAGE = """
⚠️ *Oops! Something went wrong*

Error: {error}

Please try again or use /help for assistance.
"""

POST_SUCCESS_MESSAGE = """
✅ *Post Successfully Shared!*

View your post: [Click here]({post_url})

📊 *Quick Stats*
• Time: {timestamp}
• Platform: {platform}

Want to post more? Use /post again!
"""

SCHEDULE_SUCCESS_MESSAGE = """
📅 *Post Scheduled Successfully!*

⏰ Scheduled for: *{scheduled_time}*
📱 Platform: *{platform}*

Use /status to view all scheduled posts.
"""

NO_ACCOUNT_MESSAGE = """
⚠️ *No Account Connected*

Please connect your account first:
1. Use /connect to get started
2. Choose your platform
3. Follow the authentication steps

Need help? Use /help for assistance.
"""