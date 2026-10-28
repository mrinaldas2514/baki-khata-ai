"""The privacy note a shopkeeper agrees to at registration (shown by the app, in Banglish).

Change CONSENT_VERSION whenever the note's meaning changes (and the text in
frontend/src/strings.ts, which sends this version back). New registrations must agree to the
current version; the version and time are stored with the user.

What the note promises, and where the code keeps the promise:
- entries are sent to an AI provider (Groq) to understand the sentence: app.services.parsing
- voice is sent for transcription only when the browser can't do it: POST /transcribe
- nothing is sent to the AI provider when "AI bondho rakhun" is on: users.ai_enabled
- the data is not sold or used for loans
- the shopkeeper can download everything (CSV) or delete the account at any time
"""

CONSENT_VERSION = "2026-10"
