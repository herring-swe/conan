# conan

Here I'll put my own conan recipes. Some ruthlessly based on other recipes (I will comment from where in that case).

I (currently) test builds with:
* CMake + Ninja
* Windows 11 + Visual Studio Build Tools 2022  
* Linux
  * GCC 8.2.0, 9.4.0
  * RHEL/Rocky 8.10
  * Ubuntu 22.04 LTS, Ubuntu 20.04 LTS
  * SLES 15 SP3
* Macos - If anyone knows how to get osxcross to work with conan.

With target to support:
* settings:
  * build_type: Release or Debug
* options:
  * shared: True or False

Recipes:
  * wxWidgets 3.2.5
    * There's a version on conancenter now, which I think have some flaws
      * No components
      * No ability to turn off libtiff and other image support libraries
      * Some other flags
      * No GTK 3 (waiting for default to change for gtk/system)
      * Oh and I saw plan to switch to non-system version of GTK when it's available... I will _always_ target the system's GTK.
    * Be aware that this recipe do require a lot of system packages (too many via xorg/system)