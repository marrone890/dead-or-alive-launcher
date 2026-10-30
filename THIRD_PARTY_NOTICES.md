# Project assets and third-party components

The maintainer, INFERNO-SPARTAN, approved public release of the launcher source
under MIT and confirmed redistribution permission for the supplied logo,
photographs, music, and notification icons. Those assets are included in
`app/assets/`. Their inclusion does not grant trademark ownership or imply that
a modified application is the official community launcher.

The application uses Electron, distributed under MIT. Electron's bundled
Chromium and other components have their own licences and notices. Preserve
Electron's LICENSE and LICENSES.chromium.html files in packaged distributions.
See https://github.com/electron/electron/blob/main/LICENSE.

Build dependencies include electron-builder (MIT) and Playwright (Apache-2.0).
They are used to build or test the project; their source is not claimed as
original work by this project. Dependency versions and their licences are
recorded in package-lock.json and the upstream packages.

Python service dependencies are separately licensed by their respective
authors. Their version list is in service/requirements.txt. The integration
expects an existing RedM/VORP game server; that game server, Rockstar game
content, and the RedM client are not distributed in this source repository.

SignPath approval is pending. No third-party signing service endorsement is
claimed, and no signing certificate has been provided to this project.
