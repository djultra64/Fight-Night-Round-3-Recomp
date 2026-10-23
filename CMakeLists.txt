# fnr3 - ReXGlue Recompiled Project
#
# SDK boilerplate lives in generated/rexglue.cmake.

cmake_minimum_required(VERSION 3.25)
project(fnr3 VERSION 1.0.0 DESCRIPTION "Fight Night Round 3 Recomp" LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(generated/rexglue.cmake)

# Sources
set(FNR3_SOURCES
    src/main.cpp
    src/port_graphics.cpp
    src/port_frontend.cpp
    src/port_menu.cpp
    src/port_input.cpp
    src/port_frame_times.cpp
    src/port_timing.cpp
)
# Transform only private generated copies; original codegen output is immutable.
# On the first clean build, build fnr3_codegen then reconfigure (port_build.py
# does this automatically). Unit names are discovered rather than hardcoded.
find_package(Python3 REQUIRED COMPONENTS Interpreter)
set(fnr3_timing_transform "${CMAKE_CURRENT_SOURCE_DIR}/tools/port-build/native60_transform.py")
if(REXGLUE_ENTRYPOINT_GENERATED_SOURCES)
    execute_process(
        COMMAND "${Python3_EXECUTABLE}" "${fnr3_timing_transform}"
            --input "${CMAKE_CURRENT_SOURCE_DIR}/generated/default" --list
        RESULT_VARIABLE fnr3_timing_result OUTPUT_VARIABLE fnr3_timing_units
        ERROR_VARIABLE fnr3_timing_error OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(NOT fnr3_timing_result EQUAL 0)
        message(FATAL_ERROR "Native60 source discovery failed: ${fnr3_timing_error}")
    endif()
    set(fnr3_timing_directory "${CMAKE_CURRENT_BINARY_DIR}/native60-generated")
    set(fnr3_timing_outputs "")
    set(fnr3_timing_inputs "")
    foreach(unit IN LISTS fnr3_timing_units)
        set(original "${CMAKE_CURRENT_SOURCE_DIR}/generated/default/${unit}")
        set(transformed "${fnr3_timing_directory}/${unit}")
        list(APPEND fnr3_timing_inputs "${original}")
        list(APPEND fnr3_timing_outputs "${transformed}")
        # Generator versions may emit absolute or source-relative paths.
        list(FIND REXGLUE_ENTRYPOINT_GENERATED_SOURCES "generated/default/${unit}" relative_index)
        if(NOT relative_index EQUAL -1)
            list(REMOVE_AT REXGLUE_ENTRYPOINT_GENERATED_SOURCES ${relative_index})
            list(INSERT REXGLUE_ENTRYPOINT_GENERATED_SOURCES ${relative_index} "${transformed}")
        endif()
        list(FIND REXGLUE_ENTRYPOINT_GENERATED_SOURCES "${original}" index)
        if(NOT index EQUAL -1)
            list(REMOVE_AT REXGLUE_ENTRYPOINT_GENERATED_SOURCES ${index})
            list(INSERT REXGLUE_ENTRYPOINT_GENERATED_SOURCES ${index} "${transformed}")
        endif()
        list(FIND REXGLUE_ENTRYPOINT_GENERATED_SOURCES "${transformed}" transformed_index)
        if(transformed_index EQUAL -1)
            message(FATAL_ERROR "Native60 unit missing from generated source list: ${unit}")
        endif()
    endforeach()
    add_custom_command(
        OUTPUT ${fnr3_timing_outputs}
        COMMAND "${Python3_EXECUTABLE}" "${fnr3_timing_transform}"
            --input "${CMAKE_CURRENT_SOURCE_DIR}/generated/default"
            --output "${fnr3_timing_directory}"
        DEPENDS fnr3_codegen ${fnr3_timing_inputs} "${fnr3_timing_transform}"
        COMMENT "Applying validated native gameplay/replay timing policies"
        VERBATIM)
    set_source_files_properties(${fnr3_timing_outputs}
        PROPERTIES COMPILE_OPTIONS "${REXGLUE_RECOMP_OPTIONS}")
endif()

if(WIN32)
    add_executable(fnr3 WIN32 ${FNR3_SOURCES})
else()
    add_executable(fnr3 ${FNR3_SOURCES})
endif()

rexglue_setup_target(fnr3 GPU_PLUGINS xenos)
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    target_link_options(fnr3 PRIVATE "-Wl,--export-dynamic-symbol=Fnr3GetInputGlyphBridge")
endif()

# The 0.10.0 installed SDK stages runtime libraries on Windows/macOS only.
# Linux uses $ORIGIN, so place its imported shared libraries beside the host.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    foreach(runtime_target rex::runtime rex::TracyClient)
      if(TARGET ${runtime_target})
        add_custom_command(TARGET fnr3 POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                $<TARGET_FILE:${runtime_target}>
                $<TARGET_FILE_DIR:fnr3>
            VERBATIM
        )
      endif()
    endforeach()
endif()

# An explicit override keeps local SDK fixes from being overwritten on relink.
set(FNR3_GPU_PLUGIN_FILE "" CACHE FILEPATH "Patched GPU plugin to stage beside fnr3")
if(FNR3_GPU_PLUGIN_FILE)
    if(NOT EXISTS "${FNR3_GPU_PLUGIN_FILE}")
        message(FATAL_ERROR "Patched GPU plugin does not exist: ${FNR3_GPU_PLUGIN_FILE}")
    endif()
    set(fnr3_staged_gpu "${FNR3_GPU_PLUGIN_FILE}")
else()
    set(fnr3_staged_gpu "$<TARGET_FILE:rex::gpu-xenos>")
endif()
add_custom_target(fnr3_stage_gpu ALL
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${fnr3_staged_gpu}" $<TARGET_FILE_DIR:fnr3>
    DEPENDS fnr3
    VERBATIM
)
