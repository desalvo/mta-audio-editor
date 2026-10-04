MTA Audio Editor iOS/iPadOS Core ML model resources.

Release builds may place a validated `demucs-default-4.mlmodel` or
`demucs-default-4.mlmodelc` here. The app installs this bundled baseline first,
then compares SHA-256 metadata with the configured server and updates the local
cache when a newer model is published. If the binary baseline is not bundled,
the app automatically bootstraps the default 4-stem model from the server.
