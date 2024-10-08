import glob
import json
import os
import re

from conan import ConanFile
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.env import VirtualRunEnv
from conan.tools.files import copy, get, rename, replace_in_file, rmdir
from conan.tools.microsoft import is_msvc, is_msvc_static_runtime
from conan.tools.system import package_manager

required_conan_version = ">=1.62"


class ParseCMakeError(ConanException):
    pass


def _CreateComp(name, target):
    return {
        "name": name,
        "target": target,
        "libname": "",
        "libdirs": [],
        "src_implib": "",
        "src_libloc": "",
        "src_soname": "",
        "defines": [],
        "includedirs": [],
        "requires": [],
        "system_libs": [],
        "frameworks": [],
    }


def _CompStr(comp, os=""):
    str = "       component: %s\n" % (comp["name"])
    str += "          target: %s\n" % (comp["target"])
    str += "         libname: %s\n" % (comp["libname"])
    str += "         libdirs: %s\n" % ("; ".join(comp["libdirs"]))
    # str += "      src_implib: %s\n" %(comp['src_implib'])
    # str += "      src_libloc: %s\n" %(comp['src_libloc'])
    # str += "      src_libloc: %s\n" %(comp['src_soname'])
    str += "         defines: %s\n" % ("; ".join(comp["defines"]))
    str += "     includedirs: %s\n" % ("; ".join(comp["includedirs"]))
    str += "        requires: %s\n" % ("; ".join(comp["requires"]))
    str += "     system_libs: %s\n" % (comp["system_libs"])
    if os == "Macos":
        str += "      frameworks: %s\n" % ("; ".join(comp["frameworks"]))
    return str


class wxwidgetsRecipe(ConanFile):
    name = "wxwidgets"
    # version = "3.2.5" -- see conanddata.yml
    package_type = "library"

    # Optional metadata
    license = "wxWidgets"
    # This recipe maintainer. Note this recipe is heavily modified from bincrafters:
    # https://github.com/bincrafters/community
    author = "Åke Svedin (ake.svedin@gmail.com)"
    url = "https://github.com/herring-swe/conan"
    description = (
        "wxWidgets is a C++ library that lets developers create "
        "applications for Windows, macOS, Linux and other "
        "platforms with a single code base."
    )
    homepage = "https://www.wxwidgets.org"
    topics = ("conan", "wxwidgets", "gui", "ui")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"

    """
    NOTES:
    Unsupported wxWidgets major options:
        * monolithic -> OFF (default)
        * wxUSE_STL -> OFF (default)
        * wxUSE_LIBLZMA

    To furher expand on Conan integration. These CMake packages are required
    from wxWidgets (as of 3.2.3). Listing possible conan packages to integrate to.
        Threads REQUIRED
        LibLZMA                                 (found some that maybe provide target)
        Libsecret                               (found: libsecret/0.20.5)
        Iconv                                   (found: libiconv/1.17)
        LibSoup                                 - install system packages
        Webkit 1.0
        Webkit2                                 - install system packages
        Webkit 3.0
        Fontconfig                              (found: fontconfig/2.14.2)
        GStreamer 1.0 COMPONENTS video          (found: gstreamer/1.22.3)
        GStreamer 0.1 COMPONENTS interfaces     (found: gstreamer/1.22.3)
        SDL2                                    (found: sdl/2.28.3)
        SDL
        LibNotify
        XTest
        MSPACK
        GnomeVFS2
        Qt5 COMPONENTS ...                      - Do not support
        pcre2                                   (found: pcre2/10.42)
        catch                                   (found: catch2/3.4.0)

    Integrated dependencies so far:
        OpenGL                                  opengl/system + glu/system + egl/system
                                                Note lack of GLX. FindOpenGL had problem with GLX detection before
        JPEG                                    libjpeg or (untested) libjpeg-turbo or (untested) mozjpeg
        PNG                                     libpng
        TIFF                                    libtiff (NOTE: disabled by default)
        expat                                   expat
        NanoSVG                                 nanosvg
        ZLIB                                    zlib
        X11                                     xorg/system
        GTK2                                    gtk/system - set version to 2 (default for gtk/system)
        GTK3                                    gtk/system - set version to 3
    """
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "unicode": [True, False],
        "compatibility": [
            "2.8",
            "3.0",
            "3.1",
        ],  # read somewhere it should be 3.0 and 3.2.. but nah
        "gtk": ["gtk2", "gtk3"],
        "zlib": ["off", "zlib"],
        "png": ["off", "libpng"],
        "jpeg": ["off", "libjpeg", "libjpeg-turbo", "mozjpeg"],
        "tiff": ["off", "libtiff"],
        "nanosvg": ["off", "nanosvg"],
        "expat": ["off", "expat"],
        "regex": ["off", "builtin"],  # No find module called, only use built-in or off
        "secretstore": [True, False],
        "aui": [True, False],
        "opengl": [True, False],
        "glcanvas_egl": [True, False],
        "html": [True, False],
        "mediactrl": [True, False],
        "propgrid": [True, False],
        "debugreport": [True, False],
        "ribbon": [True, False],
        "richtext": [True, False],
        "sockets": [True, False],
        "stc": [True, False],
        "webview": [True, False],
        "xml": [True, False],
        "xrc": [True, False],
        "cairo": [True, False],
        "help": [True, False],
        "html_help": [True, False],
        "url": [True, False],
        "protocol": [True, False],
        "fs_inet": [True, False],
        "custom_enables": ["ANY"],  # comma splitted list
        "custom_disables": ["ANY"],
    }

    default_options = {
        "shared": False,
        "fPIC": True,
        "unicode": True,
        "compatibility": "3.1",
        "gtk": "gtk3",
        "zlib": "zlib",
        "png": "libpng",
        "jpeg": "libjpeg",
        "tiff": "off",  # Disabled by default due to many dependecies and security notices
        "nanosvg": "nanosvg",
        "expat": "expat",
        "regex": "builtin",
        "secretstore": True,
        "aui": True,
        "opengl": True,
        "glcanvas_egl": False,  # Should be true
        "html": True,
        "mediactrl": False,  # Disabled by default as wxWidgets still uses deprecated GStreamer 0.10
        "propgrid": True,
        "debugreport": True,
        "ribbon": True,
        "richtext": True,
        "sockets": True,
        "stc": True,
        "webview": True,
        "xml": True,
        "xrc": True,
        "cairo": True,
        "help": True,
        "html_help": True,
        "url": True,
        "protocol": True,
        "fs_inet": True,
        "custom_enables": "",
        "custom_disables": "",
    }

    def validate(self):
        compat_os = ["Windows", "Linux", "Macos"]
        if self.settings.os not in compat_os:
            raise ConanInvalidConfiguration(
                "This library is only compatible with %s" % (", ".join(compat_os))
            )

    def config_options(self):
        if self.settings.os == "Windows":
            self.options.rm_safe("fPIC")
        if self.settings.os != "Linux":
            self.options.rm_safe("cairo")
            self.options.rm_safe("gtk")
            self.options.rm_safe("glcanvas_egl")

    def system_requirements(self):
        if self.settings.os != "Linux":
            # self.output.verbose("Skipping system package requirements on os: " + str(self.settings.os))
            return

        # Let's do the super duper simple "conan" way but collect all packages
        # so at least all are tried at one shot
        # Only considered the following with their respective sources
        
        # Conan is weird anyway since wtf is this? (from the docs):
        # Yum for Linux with distribution names: pidora, scientific, xenserver, amazon, oracle, amzn, almalinux or rocky
        # Dnf for Linux with distribution names: fedora, rhel, centos, mageia

        papt = []  # Ubuntu 20.04
        pyum = []  # pkgs.org: RHEL 7 or CentOS 7
        pdnf = []  # pkgs.org: RHEL 9 or Rocky 9
        pzyp = []  # pkgs.org: openSuse 15
        ppac = []  # pkgs.org: Arch

        if self.options.webview:
            # libcurl-dev is a virtual package, user must select which to install...
            papt.extend(
                ["libsoup2.4-dev", "libwebkit2gtk-4.0-dev"]
            )  # libwebkitgtk-3.0-dev too old
            pyum.extend(["libsoup-devel", "webkitgtk4-devel"])
            pdnf.extend(["libsoup-devel", "webkit2gtk3-devel"])
            pzyp.extend(["libsoup2-devel", "webkit2gtk3-soup2-devel"])
            ppac.extend(["libsoup", "webkit2gtk"])
        if self.options.secretstore:
            papt.extend(["libsecret-1-dev"])
            pyum.extend(["libsecret-devel"])
            pdnf.extend(["libsecret-devel"])
            pzyp.extend(["libsecret-devel"])
            ppac.extend(["libsecret"])
        if self.options.mediactrl:
            papt.extend(["libgstreamer0.10-dev", "libgstreamer-plugins-base0.10-dev"])
            pyum.extend(["gstreamer-devel"], ["gstreamer-plugins-base-devel"])
            # pdnf.extend(['gstreamer1-devel'], ['gstreamer1-plugins-base-devel'])
            # pzyp.extend([''], [''])  # Fixme
            # ppac.extend(['gstreamer0.10'], ['gstreamer0.10-base-plugins']) # Chaotic repo... don't count on it
        if self.options.cairo:
            papt.extend(["libcairo2-dev"])
            pyum.extend(["cairo-devel"])
            pdnf.extend(["cairo-devel"])
            pzyp.extend(["cairo-devel"])
            ppac.extend(["cairo"])

        apt = package_manager.Apt(self)
        yum = package_manager.Yum(self)
        dnf = package_manager.Dnf(self)
        zyp = package_manager.Zypper(self)
        pac = package_manager.PacMan(self)
        apt.install(papt, check=True)
        yum.install(pyum, check=True)
        dnf.install(pdnf, check=True)
        zyp.install(pzyp, check=True)
        pac.install(ppac, check=True)
        return

    def build_requirements(self):
    	self.build_requires("cmake/[>=3.29 <4]")
        self.build_requires("ninja/[>=1.10.1 <2]")

    def requirements(self):
        if self.settings.os == "Linux":
            # We only depend on these to get the necessary development packages installed
            # (although.. xorg/system isn't exacly a slim requirement)
            # Turn visible off to avoid explicitly adding 'requires' to our components.
            # Instead use the link libraries set by wx cmake
            self.requires("xorg/system", visible=False)
            self.requires("gtk/system", visible=False)
            if self.options.opengl:
                self.requires("opengl/system", visible=False)
                self.requires("glu/system", visible=False)
                if self.options.glcanvas_egl:
                    self.requires("egl/system", visible=False)
        if self.options.png == "libpng":
            self.requires("libpng/[>=1.6.43 <2]")
        if self.options.jpeg == "libjpeg":
            self.requires("libjpeg/9f")
        elif self.options.jpeg == 'libjpeg-turbo':
           self.requires('libjpeg-turbo/3.0.3')
        elif self.options.jpeg == 'mozjpeg':
           self.requires('mozjpeg/4.1.5')
        if self.options.tiff == "libtiff":
            self.requires("libtiff/4.6.0@mapdl/stable")
        if self.options.nanosvg == "nanosvg":
            self.requires("nanosvg/cci.20231025")
        if self.options.zlib == "zlib":
            self.requires("zlib/[>=1.2.13 <2]")
        if self.options.expat == "expat":
            self.requires("expat/[>=2.5.0 <3]")

    def _comp_add_require(self, name, comp):
        if name not in comp["requires"]:
            comp["requires"].append(name)

    def _comp_add_deptarget(self, name, comp):
        ld = name.lower()
        req = None
        if ld == "png::png":
            if self.options.png != "off":
                req = str(self.options.png)
        elif ld == "zlib::zlib":
            if self.options.zlib != "off":
                req = str(self.options.zlib)
        elif ld == "tiff::tiff":
            if self.options.tiff != "off":
                req = str(self.options.tiff)
        elif ld == "jpeg::jpeg":
            if self.options.jpeg != "off":
                req = str(self.options.jpeg)
        elif ld == "expat::expat":
            if self.options.expat != "off":
                req = str(self.options.expat)
        elif ld == "nanosvg::nanosvg":
            if self.options.nanosvg != "off":
                req = str(self.options.nanosvg)
        #elif ld.startswith("opengl::"):
            # Ignore targets opengl, glu, egl.. wx already link to required libraries
            # return True
        elif ld == 'opengl::opengl' or ld == 'opengl::gl':
            if self.settings.os == 'Linux' and self.options.opengl:
                req = 'opengl'
        elif ld == 'opengl::glu':
            if self.settings.os == 'Linux' and self.options.opengl:
                req = 'glu'
        elif ld == 'opengl::egl':
            if self.settings.os == 'Linux' and self.options.opengl and self.options.glcanvas_egl:
                req = 'egl'
        else:
            return False

        if req:
            self._comp_add_require(f"{req}::{req}", comp)
        return True

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

        # Ensure to use FindEXPAT.cmake instead of expat-config.cmake
        # (side effect of CMAKE_FIND_PACKAGE_PREFER_CONFIG ON, see https://github.com/conan-io/conan/issues/10387)
        replace_in_file(
            self,
            os.path.join(self.source_folder, "build", "cmake", "lib", "expat.cmake"),
            "find_package(EXPAT REQUIRED)",
            "find_package(EXPAT REQUIRED MODULE)",
        )
        replace_in_file(
            self,
            os.path.join(self.source_folder, "build", "cmake", "lib", "nanosvg.cmake"),
            "find_package(NanoSVG REQUIRED)",
            "find_package(nanosvg REQUIRED CONFIG)",
        )
        replace_in_file(
            self,
            os.path.join(self.source_folder, "build", "cmake", "lib", "nanosvg.cmake"),
            "NanoSVG::nanosvg",
            "nanosvg::nanosvg",
        )

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

        if self.settings.os == "Linux":
            self.options["gtk/system"].version = 3 if self.options.gtk == "gtk3" else 2

        if self.options.png == "libpng":
            self.options["libpng/*"].shared = self.options.shared
        if self.options.jpeg == "libjpeg":
            self.options["libjpeg/*"].shared = self.options.shared
        elif self.options.jpeg == "libjpeg-turbo":
            self.options["libjpeg-turbo/*"].shared = self.options.shared
        elif self.options.jpeg == "mozjpeg":
            self.options["mozjpeg/*"].shared = self.options.shared
        if self.options.tiff == "libtiff":
            self.options["libtiff/*"].shared = self.options.shared
        if self.options.nanosvg == "nanosvg":
            self.options["nanosvg/*"].shared = self.options.shared
        if self.options.zlib == "zlib":
            self.options["zlib/*"].shared = self.options.shared
        if self.options.expat == "expat":
            self.options["expat/*"].shared = self.options.shared

    def layout(self):
        cmake_layout(self, src_folder="src")

    def generate(self):
        def boolval(val):
            return "ON" if val else "OFF"

        tc = CMakeToolchain(self, generator="Ninja")
        tc.variables["CMAKE_FIND_DEBUG_MODE"] = "OFF"

        tc.variables["wxBUILD_OPTIMISE"] = self.settings.build_type != "Debug"
        tc.variables["wxBUILD_SHARED"] = boolval(self.options.shared)
        tc.variables["wxBUILD_SAMPLES"] = False
        tc.variables["wxBUILD_TESTS"] = False
        tc.variables["wxBUILD_DEMOS"] = False
        tc.variables["wxBUILD_INSTALL"] = True
        tc.variables["wxBUILD_COMPATIBILITY"] = self.options.compatibility
        if self.settings.compiler == "clang":
            tc.variables["wxBUILD_PRECOMP"] = False

        # platform-specific options
        if is_msvc(self):
            tc.variables["wxBUILD_USE_STATIC_RUNTIME"] = is_msvc_static_runtime(self)
            tc.variables["wxBUILD_MSVC_MULTIPROC"] = True
            tc.variables["wxBUILD_VENDOR"] = ""
        if self.settings.os == "Linux":
            tc.variables["wxBUILD_TOOLKIT"] = self.options.gtk
            tc.variables["wxUSE_CAIRO"] = self.options.cairo
            tc.variables["wxUSE_GLCANVAS_EGL"] = self.options.glcanvas_egl
        # Disable some optional libraries that will otherwise lead to non-deterministic builds
        if self.settings.os != "Windows":
            tc.variables["wxUSE_LIBSDL"] = False
            tc.variables["wxUSE_LIBICONV"] = False
            tc.variables["wxUSE_LIBNOTIFY"] = False
            tc.variables["wxUSE_LIBMSPACK"] = False
            tc.variables["wxUSE_LIBGNOMEVFS"] = False

        tc.variables["wxUSE_LIBPNG"] = "sys" if self.options.png != "off" else "OFF"
        tc.variables["wxUSE_LIBJPEG"] = "sys" if self.options.jpeg != "off" else "OFF"
        tc.variables["wxUSE_LIBTIFF"] = "sys" if self.options.tiff != "off" else "OFF"
        tc.variables["wxUSE_NANOSVG"] = (
            "sys" if self.options.nanosvg != "off" else "OFF"
        )
        tc.variables["wxUSE_ZLIB"] = "sys" if self.options.zlib != "off" else "OFF"
        tc.variables["wxUSE_EXPAT"] = "sys" if self.options.expat != "off" else "OFF"
        tc.variables["wxUSE_REGEX"] = self.options.regex

        # wxWidgets features
        tc.variables["wxUSE_UNICODE"] = self.options.unicode
        tc.variables["wxUSE_SECRETSTORE"] = self.options.secretstore

        # wxWidgets libraries
        tc.variables["wxUSE_AUI"] = self.options.aui
        tc.variables["wxUSE_OPENGL"] = self.options.opengl
        tc.variables["wxUSE_HTML"] = self.options.html
        tc.variables["wxUSE_MEDIACTRL"] = self.options.mediactrl
        tc.variables["wxUSE_PROPGRID"] = self.options.propgrid
        tc.variables["wxUSE_DEBUGREPORT"] = self.options.debugreport
        tc.variables["wxUSE_RIBBON"] = self.options.ribbon
        tc.variables["wxUSE_RICHTEXT"] = self.options.richtext
        tc.variables["wxUSE_SOCKETS"] = self.options.sockets
        tc.variables["wxUSE_STC"] = self.options.stc
        tc.variables["wxUSE_WEBVIEW"] = self.options.webview
        tc.variables["wxUSE_XML"] = self.options.xml
        tc.variables["wxUSE_XRC"] = self.options.xrc
        tc.variables["wxUSE_HELP"] = self.options.help
        tc.variables["wxUSE_WXHTML_HELP"] = self.options.html_help
        tc.variables["wxUSE_URL"] = self.options.protocol
        tc.variables["wxUSE_PROTOCOL"] = self.options.protocol
        tc.variables["wxUSE_FS_INET"] = self.options.fs_inet

        for item in str(self.options.custom_enables).split(","):
            if len(item) > 0:
                tc.variables[item] = True
        for item in str(self.options.custom_disables).split(","):
            if len(item) > 0:
                tc.variables[item] = False

        tc.generate()

        deps = CMakeDeps(self)
        deps.generate()

        ms = VirtualRunEnv(self)
        ms.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        copy(
            self,
            "LICENSE",
            src=self.source_folder,
            dst=os.path.join(self.package_folder, "licenses"),
        )
        # self.copy(pattern="LICENSE", dst="licenses", src=self._source_subfolder)
        cmake = CMake(self)
        cmake.install()

        comps = self._parse_cmake_targets(modify=True)
        # for comp in comps.values():
        #    self.output.debug(_CompStr(comp, self.settings.os))
        self.output.info("Parsed %d cmake targets" % (len(comps)))
        if "base" not in comps:
            raise ParseCMakeError("Could not parse base component")

        # Will also save comps data to package
        self._adjust_package(comps)
        return

    def package_info(self):
        comps = self._load_package_info()
        if "base" not in comps:
            # self.output.verbose(_CompStr(comps, self.settings.os))
            raise ParseCMakeError("Could not load package data")

        # self.output.debug("Read package configuration:")
        # for comp in comps.values():
        #    self.output.debug(_CompStr(comp, self.settings.os))

        for comp in comps.values():
            info = self.cpp_info.components[comp["name"]]
            info.set_property("cmake_file_name", comp["name"].capitalize())
            info.set_property("cmake_target_name", comp["target"])
            info.libs = [comp["libname"]]
            info.libdirs = ["lib"]
            info.defines = comp["defines"]
            info.includedirs = comp["includedirs"]
            info.requires = comp["requires"]
            info.system_libs = comp["system_libs"]
        return

    def _load_package_info(self):
        """
        Used from self.package_info() to read data
        """
        folder = os.path.join(self.package_folder, "pkg")
        fn = os.path.join(folder, "package_info.json")
        comps = None
        with open(fn, "r") as f:
            comps = json.load(f)
        return comps

    def _save_package_info(self, comps):
        """
        Used from self.package() to serialize parsed data
        """
        folder = os.path.join(self.package_folder, "pkg")
        fn = os.path.join(folder, "package_info.json")
        if not os.path.isdir(folder):
            os.mkdir(folder)
        with open(fn, "w") as f:
            json.dump(comps, f, indent=2)

    def _parse_syslib(self, lib):
        if self.settings.os != "Linux":
            return lib
        if not os.path.isabs(lib):
            return lib

        for name in ["libOpenGL.so", "libGLU.so", "libEGL.so"]: # "libGLX.so"
            if lib.endswith(name):
                return None
        bn = os.path.basename(lib)
        if bn.startswith("lib") and bn.endswith(".so"):
            libname = bn[3:-3]
            return libname
        return None

    def _parse_cmake_targets(self, modify=False):
        """
        Parse installed cmake files for:
          * library names (+ implib)
          * defines
          * include dirs
          * link libraries
        """

        targetsBuildFileFN = (
            "wxWidgetsTargets-" + str(self.settings.build_type).lower() + ".cmake"
        )
        targetsFileFN = "wxWidgetsTargets.cmake"
        targetsBuildFile = None
        targetsFile = None

        for root, dirs, files in os.walk(
            os.path.join(self.package_folder, "lib", "cmake", "wxWidgets")
        ):
            for file in files:
                if not targetsBuildFile and file == targetsBuildFileFN:
                    targetsBuildFile = os.path.join(root, file)
                elif not targetsFile and file == targetsFileFN:
                    targetsFile = os.path.join(root, file)
                if targetsFile and targetsBuildFile:
                    break
        if not targetsFile or not targetsBuildFile:
            raise ParseCMakeError(
                f"Could not find files: {targetsBuildFileFN} or {targetsFileFN}"
            )

        # We only support what we have seen in real wx cmake-file
        re_prop = re.compile(r"set_target_properties\(\s*([a-z\:]+)\s+.*")
        comps = {}

        def parse_wxtarget(name):
            if not name or not name.startswith("wx::wx") or len(name) < 7:
                raise ParseCMakeError
            return name[6:]

        self.output.info(f"Parsing {targetsBuildFile}...")
        with open(targetsBuildFile) as f:
            """
            Parse blocks like these
            set_target_properties(wx::wxcore PROPERTIES
              IMPORTED_IMPLIB_RELEASE "${_IMPORT_PREFIX}/lib/vc_x64_dll/wxmsw32u_core.lib"
              IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/vc_x64_dll/wxmsw32u_core_vc_custom.dll"
              )
            """

            comp = None
            for line in f:
                line = line.strip()

                if comp:
                    if line == ")":
                        comp = None
                    ## Ignore
                    # elif line.startswith('IMPORTED_LINK_INTERFACE_LANGUAGES'):
                    #    lang = line.split(' ', 1)[1].split(';')
                    #    comp['link_languages'].extend(lang)
                    elif line.startswith("IMPORTED_LOCATION"):
                        relpath = (
                            line.split(" ", 1)[1]
                            .strip('"')
                            .replace("${_IMPORT_PREFIX}/", "")
                        )
                        comp["src_libloc"] = relpath
                    elif line.startswith("IMPORTED_IMPLIB"):
                        relpath = (
                            line.split(" ", 1)[1]
                            .strip('"')
                            .replace("${_IMPORT_PREFIX}/", "")
                        )
                        comp["src_implib"] = relpath
                    elif line.startswith("IMPORTED_SONAME"):
                        # Strip any leading @rpath/
                        basename = os.path.basename(line.split(" ", 1)[1].strip('"'))
                        comp["src_soname"] = basename
                    continue

                m = re_prop.match(line)
                if m:
                    compname = parse_wxtarget(m.group(1))
                    target = "wx::" + compname
                    if compname in comps:
                        raise ParseCMakeError(f"Component {compname} already parsed")
                    comp = _CreateComp(compname, target)
                    comps[compname] = comp

        self.output.info(f"Parsing {targetsFile}...")
        with open(targetsFile) as f:
            """
            Parse blocks like these:
            set_target_properties(wx::wxcore PROPERTIES
              INTERFACE_COMPILE_DEFINITIONS "UNICODE;_UNICODE;__WXMSW__;WXUSINGDLL"
              INTERFACE_INCLUDE_DIRECTORIES "${_IMPORT_PREFIX}/lib/vc_x64_dll/mswu;${_IMPORT_PREFIX}/include"
              INTERFACE_LINK_LIBRARIES "kernel32;user32;gdi32;comdlg32;winspool;winmm;shell32;shlwapi;comctl32;ole32;oleaut32;uuid;rpcrt4;advapi32;version;ws2_32;wininet;oleacc;uxtheme;wx::wxbase"
            )
            """

            comp = None
            for line in f:
                line = line.strip()

                if comp:
                    if line == ")":
                        comp = None
                    elif line.startswith("INTERFACE_COMPILE_DEFINITIONS"):
                        defs = line[30:].strip().strip('"')
                        comp["defines"] = [d.strip() for d in defs.split(";")]
                    elif line.startswith("INTERFACE_INCLUDE_DIRECTORIES"):
                        # TODO It might be possible to instruct wx where to place 'wx/setup.h'
                        defs = (
                            line[30:]
                            .strip()
                            .strip('"')
                            .replace("${_IMPORT_PREFIX}/", "")
                        )
                        defs = defs.replace(
                            r"\$<\$<CONFIG:Debug>:d>",
                            "d" if self.settings.build_type == "Debug" else "",
                        )
                        comp["includedirs"] = [d.strip() for d in defs.split(";")]
                    elif line.startswith("INTERFACE_LINK_LIBRARIES"):
                        defs = line[25:].strip().strip('"')
                        for d in defs.split(";"):
                            d = d.strip()
                            if d.startswith(r"\$<LINK_ONLY:"):
                                d = d[13:-1]  # strip ending '>'
                            if d.startswith("wx::wx"):
                                compname = parse_wxtarget(d)
                                comp["requires"].append(compname)
                            elif "::" in d:
                                if not self._comp_add_deptarget(d, comp):
                                    self.output.warning("Unhandled require: " + d)
                                    comp["requires"].append(d)
                            elif self.settings.os == "Macos" and d.startswith(
                                "-framework"
                            ):
                                framework = d[10:].strip()
                                if framework not in comp["frameworks"]:
                                    comp["frameworks"].append(framework)
                            elif self.settings.os == "Macos" and d.endswith(
                                ".framework"
                            ):
                                framework, ext = os.path.splitext(os.path.basename(d))
                                if framework not in comp["frameworks"]:
                                    comp["frameworks"].append(framework)
                            else:
                                syslib = self._parse_syslib(d)
                                if syslib:
                                    comp["system_libs"].append(syslib)
                    continue

                m = re_prop.match(line)
                if m:
                    compname = parse_wxtarget(m.group(1))
                    if compname not in comps:
                        raise ParseCMakeError(f"Component {compname} not defined")
                    comp = comps[compname]

        return comps

    def _adjust_package(self, comps):
        """
        Try to clean up wxWidgets coherency here and prepare data for package_info()
        We want to:
            * Name all targets wx::<comp>, as is done with wxWidgets config files (but internally wx::wx<comp>)
            * Rename implib to match runtime (as basename must match in conan)
            * Move runtimes to bin and libraries to lib
            * Delete cmake-files
            * Add external dependencies when missing (shared build)
            * Serialize data to file for usage in package_info
        """

        bindir = os.path.join(self.package_folder, "bin")
        # libdir = os.path.join(self.package_folder, 'lib')

        # Get rid of any symlinks in bindir
        # Keep links in lib (soname references)
        if self.settings.os != "Windows":
            for dir in [bindir]:
                for file in os.listdir(dir):
                    fn = os.path.join(dir, file)
                    if os.path.islink(fn):
                        # self.output.verbose('Removing link: ' + fn)
                        os.unlink(fn)

        exe = ".exe" if self.settings.os == "Windows" else ""
        if not os.path.isfile(os.path.join(bindir, "wxrc" + exe)):
            matches = glob.glob(os.path.join(bindir, "wxrc*" + exe))
            if matches:
                if len(matches) > 1:
                    self.output.warning(f"Multiple wxrc{exe} found")
                m = matches[0]
                # self.output.verbose("Moving %s -> %s" %(m, os.path.join(bindir, 'wxrc'+exe)))
                rename(self, m, os.path.join(bindir, "wxrc" + exe))
            else:
                self.output.warning(f"No wxrc{exe} found")

        for comp in comps.values():
            libname = None
            libloc = comp["src_libloc"]
            implib = comp["src_implib"]
            ## TODO: Make sure soname links to library
            # soname = comp['src_soname']
            if libloc:
                ext = ""
                destdir = "lib"
                base = os.path.basename(libloc).lower()
                if self.settings.os == "Windows":
                    if self.options.shared:
                        destdir = "bin"
                    ext = ".dll" if self.options.shared else ".lib"
                elif self.settings.os == "Linux":
                    ext = ".so" if self.options.shared else ".a"
                elif self.settings.os == "Macos":
                    ext = ".dylib" if self.options.shared else ".a"
                if not base.endswith(ext):
                    if self.options.shared and self.settings.os == "Linux":
                        # Get rid of the garbage after '.so'
                        if ext not in base:
                            raise ConanException(
                                f"Invalid lib (expected *{ext}*): " + libloc
                            )
                        base = base[: base.index(ext)] + ext
                    else:
                        raise ConanException(
                            f"Invalid lib (expected *{ext}): " + libloc
                        )
                if not libname:
                    libname = base[: -len(ext)]
                dst = os.path.join(destdir, libname + ext)

                if self.settings.os == "Windows":
                    if dst != libloc:
                        # self.output.verbose("Moving %s -> %s" %(libloc, dst))
                        rename(
                            self,
                            os.path.join(self.package_folder, libloc),
                            os.path.join(self.package_folder, dst),
                        )

            if implib:
                base = os.path.basename(implib.lower())
                if self.settings.os == "Windows":
                    ext = ".lib"
                    if not base.endswith(ext):
                        raise ConanException(
                            f"Invalid implib (expected *{ext}): " + implib
                        )
                    if not libname:
                        raise ConanException(
                            f"Missing DLL for implib {base}: " + implib
                        )
                else:
                    raise ConanException(
                        "Invalid implib (not expected for OS): " + implib
                    )
                dst = os.path.join("lib", libname + ext)
                if dst != implib:
                    # self.output.verbose("Moving %s -> %s" %(implib, dst))
                    rename(
                        self,
                        os.path.join(self.package_folder, implib),
                        os.path.join(self.package_folder, dst),
                    )

            if libname:
                if self.settings.os != "Windows":
                    # Tested with Linux. Assume same with Macos
                    if not libname.startswith("lib"):
                        raise ConanException(
                            "Invalid wxWidgets library, not starting with 'lib': "
                            + implib
                        )
                    libname = libname[3:]
                comp["libname"] = libname

            # Fix for shared libraries not in requires
            # _comp_add_deptarget handles platform and settings
            if comp["name"] == "base":
                self._comp_add_deptarget("zlib::zlib", comp)
            elif comp["name"] == "core":
                self._comp_add_deptarget("jpeg::jpeg", comp)
                self._comp_add_deptarget("tiff::tiff", comp)
                self._comp_add_deptarget("png::png", comp)
                self._comp_add_deptarget("expat::expat", comp)
                self._comp_add_deptarget("nanosvg::nanosvg", comp)
            elif comp["name"] == "xml":
                self._comp_add_deptarget("expat::expat", comp)
            elif comp["name"] == "gl":
                self._comp_add_deptarget("opengl::opengl", comp)
                self._comp_add_deptarget("opengl::glu", comp)
                self._comp_add_deptarget("opengl::egl", comp)

        self._save_package_info(comps)
        rmdir(self, os.path.join(self.package_folder, "lib", "cmake"))

        return comps
