# Keep production SDK binaries portable. Project work: djultra64.
# The SDK enables INSTALL_RPATH_USE_LINK_PATH in its own directory; clear it
# after its targets exist so private SDK output paths cannot reach a package.
function(fnr3_set_sdk_loader_paths)
    # Native glyph lookup includes windows.h and the same TU uses std::min/max.
    # The SDK GPU PCH does not establish this Windows API macro boundary.
    if(WIN32 AND TARGET rexgpu-xenos)
        target_compile_definitions(rexgpu-xenos PRIVATE NOMINMAX)
    endif()
    # Public rex/ui headers expose ImGui types; source builds need its headers
    # without linking a second ImGui object instance into the application.
    if(TARGET rexruntime AND TARGET imgui)
        target_include_directories(rexruntime INTERFACE
            "$<TARGET_PROPERTY:imgui,INTERFACE_INCLUDE_DIRECTORIES>")
    endif()
    if(UNIX AND NOT APPLE)
        foreach(target rexruntime rexgpu-xenos rexglue)
            if(TARGET ${target})
                set_target_properties(${target} PROPERTIES
                    BUILD_WITH_INSTALL_RPATH TRUE
                    INSTALL_RPATH "$ORIGIN"
                    INSTALL_RPATH_USE_LINK_PATH FALSE)
            endif()
        endforeach()
    endif()
endfunction()
cmake_language(DEFER CALL fnr3_set_sdk_loader_paths)
