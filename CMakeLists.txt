cmake_minimum_required(VERSION 3.28)

set(CMAKE_CXX_STANDARD 20)

project(
	libcitygml2
	VERSION 0.1.0
	LANGUAGES CXX C)

add_subdirectory(src)

add_subdirectory(test)
