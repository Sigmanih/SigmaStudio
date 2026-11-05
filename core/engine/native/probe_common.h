#pragma once
#include "llama.h"
#include <filesystem>
#include <istream>
#include <ostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace fs = std::filesystem;

// Le librerie restano caricate fino alla fine del processo, anche nei percorsi di errore.
struct Library {
#ifdef _WIN32
    HMODULE handle;
    explicit Library(const fs::path & path) : handle(LoadLibraryW(path.wstring().c_str())) {
#else
    void * handle;
    explicit Library(const fs::path & path) : handle(dlopen(path.c_str(), RTLD_NOW | RTLD_GLOBAL)) {
#endif
        if (!handle) throw std::runtime_error("Libreria non caricabile: " + path.string());
    }
    template<class T> T symbol(const char * name) {
#ifdef _WIN32
        auto ptr = GetProcAddress(handle, name);
#else
        auto ptr = dlsym(handle, name);
#endif
        if (!ptr) throw std::runtime_error(std::string("Simbolo assente: ") + name);
        return reinterpret_cast<T>(ptr);
    }
};

template<class T> T read(std::istream & in) {
    T value{};
    if (!in.read(reinterpret_cast<char *>(&value), sizeof(value)))
        throw std::runtime_error("Ingresso troncato");
    return value;
}
template<class T> void write(std::ostream & out, const T & value) {
    out.write(reinterpret_cast<const char *>(&value), sizeof(value));
    if (!out) throw std::runtime_error("Scrittura della misura fallita");
}
template<class T> void write_vector(std::ostream & out, const std::vector<T> & value) {
    out.write(reinterpret_cast<const char *>(value.data()), value.size()*sizeof(T));
    if (!out) throw std::runtime_error("Scrittura della misura fallita");
}
