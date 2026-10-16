//go:build !windows

package cli

import (
	"errors"
	"os"
)

func makePrivate(path string, directory bool) error {
	mode := os.FileMode(0600)
	if directory {
		mode = 0700
	}
	if os.Chmod(path, mode) != nil {
		return errors.New("cannot restrict credential permissions")
	}
	return nil
}
func checkPrivate(path string, info os.FileInfo) error {
	if info.Mode().Perm()&0077 != 0 {
		return errors.New("credential file requires owner-only permissions (0600)")
	}
	return nil
}
