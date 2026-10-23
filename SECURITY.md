# Security

This app handles sensitive personal data locally. If you find a vulnerability (for example a way for a web page to read the local server, or a path traversal), please report it privately through GitHub's "Report a vulnerability" on this repository rather than a public issue. Never post your own log or claim details in an issue.

The posting lookup only reads public web pages you give it: it refuses private/loopback addresses and redirects to them, caps the page size, never follows a redirect to LinkedIn, and sends no cookies or credentials.
