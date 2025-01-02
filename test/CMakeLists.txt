include(FetchContent)

set(BUILD_GMOCK OFF)

FetchContent_Declare(
	gtest
	GIT_REPOSITORY https://github.com/google/googletest.git
	GIT_TAG v1.15.2
	EXCLUDE_FROM_ALL
	CMAKE_ARGS
		-DINSTALL_GTEST=OFF)
FetchContent_MakeAvailable(gtest)

add_executable(tests
	testsMain.cpp
)

target_link_libraries(
	tests
	PRIVATE
		gtest)
