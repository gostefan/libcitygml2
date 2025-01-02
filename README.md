# libcitygml2
C++ Library for CityGML Reading and Writing

# How to build

This project uses [CMake](https://cmake.org/) to build.

Expected prebuilt dependencies:
* libxml2

If the expected prebuilt dependency is not where CMake would expect it, provide the installation path through the `-DCMAKE_SYSTEM_PREFIX_PATH=<install path>` argument. Alternatively it can be automatically fetched and built with `-DLIBXML2_USE_PREBUILT=OFF`.

# Contributions

* The CMake project setup is inspired by [lefticus](https://github.com/lefticus)'s [cmake_template](https://github.com/cpp-best-practices/cmake_template). (Unlicense license)