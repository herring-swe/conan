#include <cstdlib>
#include <iostream>
#include <wx/utils.h>
#include <wx/init.h>
#if wxUSE_STC
#include <wx/stc/stc.h>
#endif

int main()
{
    int argc = 0;
    wxChar * argv[] = {NULL};
    if (!wxEntryStart(argc, argv)) {
        std::cerr << "wxEntryStart failed!" << std::endl;
        return EXIT_FAILURE;
    }
    wxVersionInfo vi = wxGetLibraryVersionInfo();
    std::cout << "wxWidgets version: "
              << vi.GetMajor() << "."
              << vi.GetMinor() << "."
              << vi.GetMicro() << std::endl;

//    std::cout << "Package defines:" << std::endl
//              << "WX_VER = " << WX_VER << std::endl
//              << "WX_INC = " << WX_INC << std::endl
//              << "WX_LIB = " << WX_LIB << std::endl
//              << "WX_DEF = " << WX_DEF << std::endl;

#if wxUSE_STC
    wxStyledTextCtrl * stc = new wxStyledTextCtrl();
    if(stc)
        std::cout << "Created wxStyledTextCtrl" << std::endl;
#endif
    wxEntryCleanup();
    return EXIT_SUCCESS;
}
