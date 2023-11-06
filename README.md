# conan

Here I'll put my own conan recipes. Some ruthlessly based on other recipes (I will comment from where in that case).

I (currently) only test builds with:
* CMake + Ninja
* Windows 11 + Visual Studio Build Tools 2022  
* Ubuntu 20.04 LTS (WSL2) + gcc 9.4.0
* And Macos... If anyone knows how to get osxcross to work with conan

With target to support:
* settings:
  * build_type: Release or Debug
* options:
  * shared: True or False
