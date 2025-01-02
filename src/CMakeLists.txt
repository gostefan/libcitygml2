option(BUILD_SHARED_LIBS "Build shared libraries" OFF)
option(LIBXML2_USE_PREBUILT "Should libxml2 be consumed from a prebuilt location?" OFF)
option(LIBXML2_FETCH_VERSION "Which version should be fetched? [Only used if LIBXML2_USE_PREBUILT is active.]" "v2.13.5")

if(LIBXML2_USE_PREBUILT)
	find_package(LibXml2 REQUIRED)
else()
	include(FetchContent)

	# Fetch libxml2
	FetchContent_Declare(
		libxml2
		GIT_REPOSITORY https://gitlab.gnome.org/GNOME/libxml2.git
		GIT_TAG ${LIBXML2_FETCH_VERSION}
		EXCLUDE_FROM_ALL
	)
	set(LIBXML2_WITH_ICONV OFF)
	set(LIBXML2_WITH_PYTHON OFF)
	FetchContent_MakeAvailable(libxml2)
endif()

add_library(libcitygml2
	main.cpp)

target_link_libraries(libcitygml2 PRIVATE LibXml2::LibXml2)
