//go:build !production || darwin

package main

// Development builds look for Artemis-<plat>.zip or Artemis-portable-<plat>-*.zip
// beside the executable. macOS production copies the zip into Resources as
// Artemis-<plat>.zip.
var embeddedPortable []byte
