# Dead or Alive Launcher

Windows community launcher for the Dead or Alive RedM server, maintained by
[INFERNO-SPARTAN / marrone890](https://github.com/marrone890).

The source code is released under the [MIT licence](LICENSE). The current
Windows launcher is unsigned. SignPath signing has not been granted.

The launcher opens RedM, displays public lobbies, accepts private lobby codes,
and supports global, friend, and guild messaging. Player accounts are linked by
a short-lived code generated in-game. It uses the existing RedM voice service.
It requires a legitimate installation of RDR2, RedM, and Steam.

The client, companion API, schema, and small game integration are included.
The game server, gameplay resources, databases, player information, credentials,
TLS private keys, build output, and dependency folders are not included.

## Build

Use Node.js 26 on Windows x64. Run `npm ci`,
`node node_modules/electron/install.js`, and `npm run dist`.
The output is `release/DeadOrAlive-Launcher-1.0.0.exe`.
The GitHub Actions workflow builds the unsigned portable application and uploads
it as an artifact; it does not publish releases or request signing.

The production API hostname and public certificate fingerprint in
`app/connection.json` are public client connection settings, not credentials.
The private certificate key and database settings must remain on the server.

## Privacy

See [the privacy policy](PRIVACY.md) for automatic status requests, account
linking, stored chat messages, external services, and local session storage.

## Code signing policy

See [the code signing policy](CODE_SIGNING_POLICY.md).
The current Windows build is unsigned. An application to SignPath Foundation
is being prepared; this is not an approval, endorsement, or signing commitment.

## Project and releases

- [Source and homepage](https://github.com/marrone890/dead-or-alive-launcher)
- [Downloads](https://github.com/marrone890/dead-or-alive-launcher/releases)
- [Builds](https://github.com/marrone890/dead-or-alive-launcher/actions)

The maintainer has approved MIT publication and confirmed public redistribution
permission for the supplied artwork, photographs, icons, and music. See
[third-party notices](THIRD_PARTY_NOTICES.md). The source project does not grant
ownership of the community's name or imply endorsement of modified versions.

Signing approval still requires SignPath's review, confirmation of GitHub
multi-factor authentication, and manual release approval by the maintainer.

The source is a new project, and no independent reputation or download statistics
are claimed. SignPath Foundation makes its own eligibility decision.
