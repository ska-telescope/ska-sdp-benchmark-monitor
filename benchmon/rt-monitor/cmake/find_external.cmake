function(find_external NAME)
  cmake_parse_arguments(ARG "" "GIT_REPOSITORY;GIT_TAG" "DEPENDENCIES" ${ARGN})

  if(NOT ARG_GIT_REPOSITORY)
    message(FATAL_ERROR "GIT_REPOSITORY is required for find_external(${NAME})")
  endif()
  if(NOT ARG_GIT_TAG)
    message(FATAL_ERROR "GIT_TAG is required for find_external(${NAME})")
  endif()

  find_package(${NAME} QUIET)
  if(NOT ${${NAME}_FOUND})
    foreach(dependency ${ARG_DEPENDENCIES})
      set(CMAKE_PREFIX_PATH ${CMAKE_PREFIX_PATH} ${${dependency}_SOURCE_DIR}
                            ${${dependency}_BINARY_DIR})
    endforeach()
    FetchContent_Declare(
      ${NAME}
      GIT_REPOSITORY ${ARG_GIT_REPOSITORY}
      GIT_TAG ${ARG_GIT_TAG})
    FetchContent_MakeAvailable(${NAME})
  endif()
endfunction()
