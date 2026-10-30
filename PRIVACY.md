# Privacy policy

Draft for the Dead or Alive Launcher. Review with the maintainer before publication.

## Network connections

The launcher automatically checks the Dead or Alive companion service at
45.14.187.72:30121 for server status and public lobbies. Like other network
connections, this exposes the connecting IP address to the service and its host.
The service connection uses encrypted TLS with a certificate pinned in the app.
The current build begins these status checks when opened; closing the launcher
stops its requests. No optional analytics or advertising SDK is included.

Player linking is optional. Players explicitly request a short-lived code using
`/launcher` in-game and enter it in the app. The game integration associates their
game licence identifier and player display name with a companion account. The
launcher never asks for Steam, Rockstar, or Discord passwords.

## Messages and accounts

The companion service stores account identifiers, display names, friendship
requests and blocks, guild membership, submitted messages and timestamps, and
pending lobby joins. Game presence updates indicate whether a linked account is
in-game. The service checks friendship and guild membership to restrict private
chat access. Messages are not end-to-end encrypted; the server operator can
access the database.

Messages, account records, and backups do not currently have a fixed automatic
deletion period. Contact the maintainer privately to request deletion or clarify
retention. Do not publish identifiers or private chat in public GitHub issues.

## Local data and sign-out

The app stores its session token using Windows-backed Electron safeStorage
encryption. The server stores a hash rather than the raw bearer token. Sessions
expire after 30 days. Sign out in Community to remove the local saved login and
revoke that session. `/launcher revoke` in-game revokes all launcher sessions for
that player. Music volume is saved locally.

The portable executable extracts application files to a temporary directory and
saves preferences/session information in the user's application-data folder.
To remove the launcher, sign out, close it, delete the portable executable, and
remove the Dead or Alive application-data folder if no other app uses it.

## Other services

Play RedM opens the installed RedM client, which has its own game/network
behaviour. Discord and website buttons open those external services only when
selected. Their policies apply independently:

- Cfx.re / RedM: https://fivem.net/privacy
- Discord: https://discord.com/privacy
- Community website: https://www.doapvp.it/

## Contact

Maintainer: INFERNO-SPARTAN / https://github.com/marrone890.
Private contact can be arranged through the community Discord:
https://discord.com/invite/caVCQcvJMG. A dedicated privacy email has not yet
been supplied for this draft.
