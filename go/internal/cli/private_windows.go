package cli

import (
	"errors"
	"os"

	"golang.org/x/sys/windows"
)

func makePrivate(path string, directory bool) error {
	user, err := windows.GetCurrentProcessToken().GetTokenUser()
	if err != nil {
		return errors.New("cannot resolve credential owner")
	}
	flags := ""
	if directory {
		flags = "OICI"
	}
	descriptor, err := windows.SecurityDescriptorFromString("D:P(A;" + flags + ";FA;;;" + user.User.Sid.String() + ")(A;" + flags + ";FA;;;SY)")
	if err != nil {
		return errors.New("cannot create credential ACL")
	}
	acl, _, err := descriptor.DACL()
	if err != nil {
		return errors.New("cannot read credential ACL")
	}
	if windows.SetNamedSecurityInfo(path, windows.SE_FILE_OBJECT, windows.DACL_SECURITY_INFORMATION|windows.PROTECTED_DACL_SECURITY_INFORMATION, nil, nil, acl, nil) != nil {
		return errors.New("cannot restrict credential ACL")
	}
	return nil
}
func checkPrivate(path string, info os.FileInfo) error { return makePrivate(path, false) }
