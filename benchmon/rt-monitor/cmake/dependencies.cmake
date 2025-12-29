set(FETCHCONTENT_BASE_DIR "${CMAKE_BINARY_DIR}/_deps")
set(FETCHCONTENT_UPDATES_DISCONNECTED ON)
set(CPR_USE_SYSTEM_CURL ON)

include(FetchContent)
include(find_external)

find_package(OpenSSL REQUIRED)
find_package(ICU COMPONENTS uc data i18n io)


# Try to find system Boost first
find_package(Boost)
if(Boost_FOUND)
  message(STATUS "Found system Boost: ${Boost_INCLUDE_DIRS}")
  if(NOT TARGET Boost::boost)
    add_library(Boost::boost INTERFACE IMPORTED)
    set_target_properties(Boost::boost PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${Boost_INCLUDE_DIRS}")
  endif()
else()
  message(STATUS "System Boost not found, downloading...")
  FetchContent_Declare(
    Boost
    GIT_REPOSITORY "https://github.com/boostorg/boost.git"
    GIT_TAG "boost-1.85.0"
    GIT_PROGRESS ON
    GIT_SHALLOW ON
    OVERRIDE_FIND_PACKAGE TRUE EXCLUDE_FROM_ALL)
  FetchContent_MakeAvailable(Boost)
  
  if(NOT TARGET Boost::boost)
    add_library(Boost::boost INTERFACE IMPORTED)
    set_target_properties(Boost::boost PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${boost_SOURCE_DIR}")
  endif()
endif()



# Try to find system CURL
find_package(CURL REQUIRED)
if(CURL_FOUND)
  message(STATUS "Found system CURL: ${CURL_INCLUDE_DIRS}")
endif()


# Try to find system spdlog first
find_package(spdlog QUIET)
if(spdlog_FOUND)
  message(STATUS "Found system spdlog")
else()
  message(STATUS "System spdlog not found, downloading...")
  FetchContent_Declare(
    spdlog
    GIT_REPOSITORY https://github.com/gabime/spdlog.git
    GIT_TAG 486b55554f11c9cccc913e11a87085b2a91f706f)
  FetchContent_MakeAvailable(spdlog)
endif()

# scn removed

# Try to find system scn first
# find_package(scn QUIET)
# if(scn_FOUND)
#   message(STATUS "Found system scn")
# else()
#   message(STATUS "System scn not found, downloading...")
#   FetchContent_MakeAvailable(scn)
# endif()

# influxdb-cxx removed
