#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <dinput.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>


namespace {

constexpr UINT kChineseCodePage = 936;
constexpr char kLanguagePodMountName[] = "LANGUAGE.POD";
HMODULE g_self = nullptr;
HMODULE g_real_dinput8 = nullptr;
unsigned g_patch_mask = 0;

using BitFontDrawFn = int(__thiscall*)(
    void*, const char*, int, int, DWORD, int);
using DirectInput8CreateFn = HRESULT(WINAPI*)(
    HINSTANCE, DWORD, REFIID, LPVOID*, LPUNKNOWN);
using DllCanUnloadNowFn = HRESULT(WINAPI*)();
using DllGetClassObjectFn = HRESULT(WINAPI*)(REFCLSID, REFIID, LPVOID*);
using DllRegisterServerFn = HRESULT(WINAPI*)();
using GetdfDIJoystickFn = LPCDIDATAFORMAT(WINAPI*)();

BitFontDrawFn g_original_bit_font_draw = nullptr;

constexpr unsigned char kCarrierLeadMinimum = 0x81;
constexpr unsigned char kCarrierLeadMaximum = 0x9F;
constexpr unsigned char kCarrierTailMinimum = 0xA1;
constexpr unsigned char kCarrierTailMaximum = 0xFE;
constexpr int kCarrierTailCount =
    kCarrierTailMaximum - kCarrierTailMinimum + 1;
constexpr int kChineseAtlasWidth = 2048;
constexpr int kChineseAtlasHeight = 4096;
constexpr int kChineseAtlasBaseY = 256;
constexpr int kChineseCellWidth = 34;
constexpr int kChineseRowPitch = 39;
constexpr int kChineseGlyphWidth = 32;
constexpr int kChineseGlyphHeight = 37;
constexpr int kChineseAtlasColumns =
    kChineseAtlasWidth / kChineseCellWidth;
constexpr size_t kBitFontNameOffset = 0x240C;


struct BitGlyphRecord {
    int x;
    int y;
    int width;
    int height;
    int vertical_offset;
    float u0;
    float v0;
    float u1;
    float v1;
};

static_assert(sizeof(BitGlyphRecord) == 36, "Unexpected bit-font glyph size");


struct DynamicSlot {
    std::uint16_t code;
    unsigned char slot;
};


bool IsChineseBitFont(void* object) {
    const auto* name = reinterpret_cast<const unsigned char*>(object)
        + kBitFontNameOffset;
    constexpr char needle[] = "gothictitle_ru";
    constexpr size_t needle_length = sizeof(needle) - 1;
    for (size_t start = 0; start + needle_length <= 64; ++start) {
        bool match = true;
        for (size_t index = 0; index < needle_length; ++index) {
            unsigned char value = name[start + index];
            if (value == 0) {
                return false;
            }
            if (value >= 'A' && value <= 'Z') {
                value = static_cast<unsigned char>(value - 'A' + 'a');
            }
            if (value != static_cast<unsigned char>(needle[index])) {
                match = false;
                break;
            }
        }
        if (match) {
            return true;
        }
    }
    return false;
}


void SetDynamicGlyph(
    void* object, unsigned char slot, int atlas_index) {
    const int column = atlas_index % kChineseAtlasColumns;
    const int row = atlas_index / kChineseAtlasColumns;
    BitGlyphRecord record = {};
    record.x = column * kChineseCellWidth;
    record.y = kChineseAtlasBaseY + row * kChineseRowPitch;
    record.width = kChineseGlyphWidth;
    record.height = kChineseGlyphHeight;
    record.vertical_offset = 0;
    record.u0 = static_cast<float>(record.x)
        / static_cast<float>(kChineseAtlasWidth);
    record.v0 = static_cast<float>(record.y)
        / static_cast<float>(kChineseAtlasHeight);
    record.u1 = static_cast<float>(record.x + record.width)
        / static_cast<float>(kChineseAtlasWidth);
    record.v1 = static_cast<float>(record.y + record.height)
        / static_cast<float>(kChineseAtlasHeight);

    auto* glyphs = reinterpret_cast<BitGlyphRecord*>(
        reinterpret_cast<unsigned char*>(object) + 4);
    glyphs[slot] = record;
}


bool PrepareDynamicText(
    void* object, const char* text, std::vector<char>* output) {
    if (text == nullptr || !IsChineseBitFont(object)) {
        return false;
    }

    output->clear();
    output->reserve(strlen(text) + 1);
    std::vector<DynamicSlot> assignments;
    assignments.reserve(kCarrierTailCount);
    bool found = false;
    const auto* cursor = reinterpret_cast<const unsigned char*>(text);
    while (*cursor != 0) {
        const unsigned char lead = cursor[0];
        const unsigned char tail = cursor[1];
        if (
            lead >= kCarrierLeadMinimum
            && lead <= kCarrierLeadMaximum
            && tail >= kCarrierTailMinimum
            && tail <= kCarrierTailMaximum) {
            found = true;
            const std::uint16_t code = static_cast<std::uint16_t>(
                (static_cast<unsigned>(lead) << 8) | tail);
            auto assignment = std::find_if(
                assignments.begin(),
                assignments.end(),
                [code](const DynamicSlot& item) {
                    return item.code == code;
                });
            if (assignment == assignments.end()) {
                if (assignments.size()
                    >= static_cast<size_t>(kCarrierTailCount)) {
                    output->push_back('?');
                    cursor += 2;
                    continue;
                }
                const unsigned char slot = static_cast<unsigned char>(
                    kCarrierTailMinimum + assignments.size());
                assignments.push_back({code, slot});
                assignment = assignments.end() - 1;
                const int atlas_index =
                    (lead - kCarrierLeadMinimum) * kCarrierTailCount
                    + (tail - kCarrierTailMinimum);
                SetDynamicGlyph(object, slot, atlas_index);
            }
            // The renderer indexes one byte at a time.  0x81 deliberately has
            // no FNT record, while the following dynamic slot carries the
            // complete glyph.  Width calculations on the original carrier
            // string see the same zero-width lead plus one full-width tail.
            output->push_back(static_cast<char>(kCarrierLeadMinimum));
            output->push_back(static_cast<char>(assignment->slot));
            cursor += 2;
            continue;
        }
        output->push_back(static_cast<char>(*cursor));
        ++cursor;
    }
    output->push_back('\0');
    return found;
}


#include "fmv_layout.h"

int __fastcall DynamicBitFontDraw(
    void* object,
    void*,
    const char* text,
    int x,
    int y,
    DWORD color,
    int shadow) {
    if (g_original_bit_font_draw == nullptr) {
        return 0;
    }
    static thread_local bool inside = false;
    static thread_local std::vector<char> transformed;
    if (inside) {
        return g_original_bit_font_draw(
            object, text, x, y, color, shadow);
    }
    try {
        if (!PrepareDynamicText(object, text, &transformed)) {
            return g_original_bit_font_draw(
                object, text, x, y, color, shadow);
        }
        inside = true;
        const int result = g_original_bit_font_draw(
            object, transformed.data(), x, y, color, shadow);
        inside = false;
        return result;
    } catch (...) {
        inside = false;
        return g_original_bit_font_draw(
            object, text, x, y, color, shadow);
    }
}


HMODULE LoadRealDinput8() {
    if (g_real_dinput8 != nullptr) {
        return g_real_dinput8;
    }
    wchar_t system_directory[MAX_PATH] = {};
    const UINT length = GetSystemDirectoryW(system_directory, MAX_PATH);
    if (length == 0 || length >= MAX_PATH - 13) {
        return nullptr;
    }
    std::wstring path(system_directory, length);
    path += L"\\dinput8.dll";
    g_real_dinput8 = LoadLibraryW(path.c_str());
    return g_real_dinput8;
}


FARPROC ResolveReal(const char* name) {
    HMODULE module = LoadRealDinput8();
    return module == nullptr ? nullptr : GetProcAddress(module, name);
}


std::wstring ConvertChinese(const char* text, int byte_count) {
    if (text == nullptr || byte_count == 0) {
        return {};
    }
    const int wide_count = MultiByteToWideChar(
        kChineseCodePage, 0, text, byte_count, nullptr, 0);
    if (wide_count <= 0) {
        return {};
    }
    std::wstring result(static_cast<size_t>(wide_count), L'\0');
    if (MultiByteToWideChar(
            kChineseCodePage,
            0,
            text,
            byte_count,
            result.data(),
            wide_count) != wide_count) {
        return {};
    }
    return result;
}


BOOL WINAPI ChineseIsDBCSLeadByte(BYTE value) {
    return IsDBCSLeadByteEx(kChineseCodePage, value);
}


HFONT WINAPI ChineseCreateFontA(
    int height,
    int width,
    int escapement,
    int orientation,
    int weight,
    DWORD italic,
    DWORD underline,
    DWORD strike_out,
    DWORD char_set,
    DWORD output_precision,
    DWORD clip_precision,
    DWORD quality,
    DWORD pitch_and_family,
    LPCSTR face_name) {
    std::wstring face = ConvertChinese(face_name, -1);
    if (face.empty() && face_name != nullptr && *face_name != '\0') {
        const int count = MultiByteToWideChar(
            CP_ACP, 0, face_name, -1, nullptr, 0);
        if (count > 0) {
            face.resize(static_cast<size_t>(count));
            MultiByteToWideChar(
                CP_ACP, 0, face_name, -1, face.data(), count);
        }
    }
    return CreateFontW(
        height,
        width,
        escapement,
        orientation,
        weight,
        italic,
        underline,
        strike_out,
        GB2312_CHARSET,
        output_precision,
        clip_precision,
        quality,
        pitch_and_family,
        face.empty() ? L"Microsoft YaHei UI" : face.c_str());
}


BOOL WINAPI ChineseTextOutA(
    HDC dc, int x, int y, LPCSTR text, int byte_count) {
    std::wstring wide = ConvertChinese(text, byte_count);
    if (byte_count > 0 && wide.empty()) {
        return TextOutA(dc, x, y, text, byte_count);
    }
    return TextOutW(
        dc, x, y, wide.data(), static_cast<int>(wide.size()));
}


BOOL WINAPI ChineseExtTextOutA(
    HDC dc,
    int x,
    int y,
    UINT options,
    const RECT* rectangle,
    LPCSTR text,
    UINT byte_count,
    const INT* spacing) {
    if ((options & ETO_GLYPH_INDEX) != 0) {
        return ExtTextOutA(
            dc, x, y, options, rectangle, text, byte_count, spacing);
    }
    std::wstring wide = ConvertChinese(text, static_cast<int>(byte_count));
    if (byte_count > 0 && wide.empty()) {
        return ExtTextOutA(
            dc, x, y, options, rectangle, text, byte_count, spacing);
    }
    return ExtTextOutW(
        dc,
        x,
        y,
        options,
        rectangle,
        wide.data(),
        static_cast<UINT>(wide.size()),
        nullptr);
}


BOOL WINAPI ChineseGetTextExtentPoint32A(
    HDC dc, LPCSTR text, int byte_count, LPSIZE size) {
    std::wstring wide = ConvertChinese(text, byte_count);
    if (byte_count > 0 && wide.empty()) {
        return GetTextExtentPoint32A(dc, text, byte_count, size);
    }
    return GetTextExtentPoint32W(
        dc, wide.data(), static_cast<int>(wide.size()), size);
}


bool PatchImport(
    HMODULE image,
    const char* imported_dll,
    const char* imported_name,
    void* replacement) {
    auto* base = reinterpret_cast<unsigned char*>(image);
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return false;
    }
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return false;
    }
    const IMAGE_DATA_DIRECTORY& import_directory =
        nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (import_directory.VirtualAddress == 0) {
        return false;
    }

    auto* descriptor = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(
        base + import_directory.VirtualAddress);
    for (; descriptor->Name != 0; ++descriptor) {
        const char* module_name =
            reinterpret_cast<const char*>(base + descriptor->Name);
        if (_stricmp(module_name, imported_dll) != 0) {
            continue;
        }

        const DWORD names_rva = descriptor->OriginalFirstThunk != 0
            ? descriptor->OriginalFirstThunk
            : descriptor->FirstThunk;
        auto* names = reinterpret_cast<IMAGE_THUNK_DATA*>(base + names_rva);
        auto* addresses = reinterpret_cast<IMAGE_THUNK_DATA*>(
            base + descriptor->FirstThunk);
        for (; names->u1.AddressOfData != 0; ++names, ++addresses) {
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) {
                continue;
            }
            auto* import = reinterpret_cast<IMAGE_IMPORT_BY_NAME*>(
                base + names->u1.AddressOfData);
            if (strcmp(
                    reinterpret_cast<const char*>(import->Name),
                    imported_name) != 0) {
                continue;
            }

            DWORD old_protection = 0;
            if (!VirtualProtect(
                    &addresses->u1.Function,
                    sizeof(addresses->u1.Function),
                    PAGE_READWRITE,
                    &old_protection)) {
                return false;
            }
            addresses->u1.Function =
                reinterpret_cast<ULONG_PTR>(replacement);
            DWORD ignored = 0;
            VirtualProtect(
                &addresses->u1.Function,
                sizeof(addresses->u1.Function),
                old_protection,
                &ignored);
            FlushInstructionCache(
                GetCurrentProcess(),
                &addresses->u1.Function,
                sizeof(addresses->u1.Function));
            return true;
        }
    }
    return false;
}


bool WriteProtectedMemory(
    void* address, const void* replacement, size_t byte_count) {
    DWORD old_protection = 0;
    if (!VirtualProtect(
            address,
            byte_count,
            PAGE_EXECUTE_READWRITE,
            &old_protection)) {
        return false;
    }
    memcpy(address, replacement, byte_count);
    DWORD ignored = 0;
    VirtualProtect(address, byte_count, old_protection, &ignored);
    FlushInstructionCache(GetCurrentProcess(), address, byte_count);
    return true;
}


void WriteRelativeJump(
    unsigned char* instruction, const void* destination,
    const void* execution_address) {
    instruction[0] = 0xE9;
    // The output buffer may be on the stack. E9 is relative to where those
    // bytes execute, not where we construct them. x86 rel32 wraps modulo 2^32.
    const std::uint32_t relative =
        static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(destination))
        - static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(execution_address) + 5);
    memcpy(instruction + 1, &relative, sizeof(relative));
}


bool PatchDynamicBitFontRenderer(HMODULE image) {
    // CBitFont::drawText in the clean 2026 Terminal Cut executable.
    // The first three complete instructions occupy six bytes:
    //   push ebp
    //   mov  ebp, esp
    //   mov  eax, [ebp+18h]
    constexpr size_t kBitFontDrawRva = 0xE6AB0;
    constexpr unsigned char kExpected[] = {
        0x55, 0x8B, 0xEC, 0x8B, 0x45, 0x18,
    };
    constexpr size_t kPatchLength = sizeof(kExpected);
    auto* target = reinterpret_cast<unsigned char*>(image)
        + kBitFontDrawRva;
    if (memcmp(target, kExpected, kPatchLength) != 0) {
        return false;
    }

    auto* trampoline = reinterpret_cast<unsigned char*>(
        VirtualAlloc(
            nullptr,
            kPatchLength + 5,
            MEM_COMMIT | MEM_RESERVE,
            PAGE_EXECUTE_READWRITE));
    if (trampoline == nullptr) {
        return false;
    }
    memcpy(trampoline, target, kPatchLength);
    WriteRelativeJump(
        trampoline + kPatchLength, target + kPatchLength,
        trampoline + kPatchLength);
    FlushInstructionCache(GetCurrentProcess(), trampoline, kPatchLength + 5);

    unsigned char replacement[kPatchLength] = {};
    WriteRelativeJump(
        replacement,
        reinterpret_cast<void*>(&DynamicBitFontDraw), target);
    for (size_t index = 5; index < kPatchLength; ++index) {
        replacement[index] = 0x90;
    }
    g_original_bit_font_draw = reinterpret_cast<BitFontDrawFn>(trampoline);
    if (!WriteProtectedMemory(target, replacement, kPatchLength)) {
        g_original_bit_font_draw = nullptr;
        VirtualFree(trampoline, 0, MEM_RELEASE);
        return false;
    }
    return true;
}


bool PatchEnglishVoiceBranch(HMODULE image) {
    // rayne2.exe SHA-256:
    // EAE3925A344668500F3533EBEC146376C8B1BBDB168ED2C3B1D4DECB0ABF0952
    // VA 00549154: JNE EnglishSoundBranch -> JMP EnglishSoundBranch.
    constexpr size_t kVoiceBranchRva = 0x149154;
    constexpr unsigned char kExpected[] = {0x75, 0x45};
    constexpr unsigned char kReplacement[] = {0xEB, 0x45};
    auto* address = reinterpret_cast<unsigned char*>(image)
        + kVoiceBranchRva;
    if (memcmp(address, kExpected, sizeof(kExpected)) != 0) {
        return false;
    }
    return WriteProtectedMemory(
        address, kReplacement, sizeof(kReplacement));
}


bool PatchLanguageBeforeArt(HMODULE image) {
    // The POD manager searches archives from the first mounted archive to the
    // last.  The clean executable mounts W32ART.POD first and LANGUAGE.POD
    // fifth.  The Chinese LANGUAGE.POD embeds only two duplicate font assets,
    // so swapping these two mount names makes the language-owned fonts win
    // without changing any modded W32ART content on disk.
    static_assert(sizeof(void*) == 4, "Proxy must be built for x86");
    constexpr size_t kArtFormatPushRva = 0x1A4B68;
    constexpr size_t kArtFormatRva = 0x310694;
    constexpr size_t kLanguageLiteralRva = 0x3106C4;
    constexpr unsigned char kW32ArtLiteral[13] = {
        'W', '3', '2', 'A', 'R', 'T', '.', 'P', 'O', 'D', 0, 0, 0,
    };
    constexpr unsigned char kExpectedLanguageLiteral[13] = {
        'L', 'A', 'N', 'G', 'U', 'A', 'G', 'E', '.', 'P', 'O', 'D', 0,
    };

    auto* base = reinterpret_cast<unsigned char*>(image);
    auto* push = base + kArtFormatPushRva;
    auto* language_literal = base + kLanguageLiteralRva;
    unsigned char expected_push[5] = {0x68, 0, 0, 0, 0};
    unsigned char replacement_push[5] = {0x68, 0, 0, 0, 0};
    const DWORD expected_art_format = static_cast<DWORD>(
        reinterpret_cast<ULONG_PTR>(base + kArtFormatRva));
    const DWORD replacement_language = static_cast<DWORD>(
        reinterpret_cast<ULONG_PTR>(kLanguagePodMountName));
    memcpy(expected_push + 1, &expected_art_format, sizeof(DWORD));
    memcpy(replacement_push + 1, &replacement_language, sizeof(DWORD));

    if (memcmp(push, expected_push, sizeof(expected_push)) != 0
        || memcmp(
               language_literal,
               kExpectedLanguageLiteral,
               sizeof(kExpectedLanguageLiteral)) != 0) {
        return false;
    }
    if (!WriteProtectedMemory(
            language_literal,
            kW32ArtLiteral,
            sizeof(kW32ArtLiteral))) {
        return false;
    }
    if (!WriteProtectedMemory(
            push,
            replacement_push,
            sizeof(replacement_push))) {
        WriteProtectedMemory(
            language_literal,
            kExpectedLanguageLiteral,
            sizeof(kExpectedLanguageLiteral));
        return false;
    }
    return true;
}


bool PatchFmvWrapping(HMODULE image) {
    // Redirect just the movie-player wrap call, not the shared wrap function.
    auto* base=reinterpret_cast<unsigned char*>(image);
    auto* call=base+0x28EB00;
    if(call[0]!=0xE8) return false;
    std::int32_t old_offset=0;
    memcpy(&old_offset,call+1,4);
    const DWORD destination=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(call+5))+static_cast<DWORD>(old_offset);
    if(destination!=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(base+0xE5A90))) return false;
    unsigned char replacement[5]={0xE8,0,0,0,0};
    const DWORD delta=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(&FmvChineseWrap))-
        static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(call+5));
    memcpy(replacement+1,&delta,4);
    g_original_fmv_wrap=reinterpret_cast<FmvWrapFn>(base+0xE5A90);
    if(!WriteProtectedMemory(call,replacement,5)) {g_original_fmv_wrap=nullptr;return false;}
    return true;
}

void InstallChineseHooks() {
    HMODULE image = GetModuleHandleW(nullptr);
    if (PatchImport(
            image,
            "KERNEL32.dll",
            "IsDBCSLeadByte",
            reinterpret_cast<void*>(&ChineseIsDBCSLeadByte))) {
        g_patch_mask |= 1u << 0;
    }
    if (PatchImport(
            image,
            "GDI32.dll",
            "CreateFontA",
            reinterpret_cast<void*>(&ChineseCreateFontA))) {
        g_patch_mask |= 1u << 1;
    }
    if (PatchImport(
            image,
            "GDI32.dll",
            "TextOutA",
            reinterpret_cast<void*>(&ChineseTextOutA))) {
        g_patch_mask |= 1u << 2;
    }
    if (PatchImport(
            image,
            "GDI32.dll",
            "ExtTextOutA",
            reinterpret_cast<void*>(&ChineseExtTextOutA))) {
        g_patch_mask |= 1u << 3;
    }
    if (PatchImport(
            image,
            "GDI32.dll",
            "GetTextExtentPoint32A",
            reinterpret_cast<void*>(&ChineseGetTextExtentPoint32A))) {
        g_patch_mask |= 1u << 4;
    }
    if (PatchEnglishVoiceBranch(image)) {
        g_patch_mask |= 1u << 5;
    }
    if (PatchLanguageBeforeArt(image)) {
        g_patch_mask |= 1u << 6;
    }
    if (PatchFmvWrapping(image)) {
        g_patch_mask |= 1u << 8;
    }
    if (PatchDynamicBitFontRenderer(image)) {
        g_patch_mask |= 1u << 7;
    }
}


void WriteStatusLog() {
    wchar_t module_path[MAX_PATH] = {};
    const DWORD length = GetModuleFileNameW(g_self, module_path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return;
    }
    std::wstring path(module_path, length);
    const size_t separator = path.find_last_of(L"\\/");
    if (separator == std::wstring::npos) {
        return;
    }
    path.resize(separator);
    path += L"\\_cn_project\\logs\\dinput8_proxy.log";
    HANDLE file = CreateFileW(
        path.c_str(),
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE) {
        return;
    }
    char line[256] = {};
    const int count = wsprintfA(
        line,
        "pid=%lu patch_mask=0x%02X code_page=%u voice=%s "
        "font_archive=%s dynamic_font=%s fmv_wrap=%s\r\n",
        GetCurrentProcessId(),
        g_patch_mask,
        kChineseCodePage,
        (g_patch_mask & (1u << 5)) != 0 ? "EN" : "native",
        (g_patch_mask & (1u << 6)) != 0
            ? "LANGUAGE_FIRST"
            : "native_order",
        (g_patch_mask & (1u << 7)) != 0
            ? "on"
            : "off",
        (g_patch_mask & (1u << 8)) != 0 ? "on" : "off");
    DWORD written = 0;
    WriteFile(file, line, static_cast<DWORD>(count), &written, nullptr);
    CloseHandle(file);
}

}  // namespace


extern "C" HRESULT WINAPI DirectInput8Create(
    HINSTANCE instance,
    DWORD version,
    REFIID interface_id,
    LPVOID* output,
    LPUNKNOWN outer) {
    auto function = reinterpret_cast<DirectInput8CreateFn>(
        ResolveReal("DirectInput8Create"));
    if (function == nullptr) {
        return E_FAIL;
    }
    WriteStatusLog();
    return function(instance, version, interface_id, output, outer);
}


extern "C" HRESULT WINAPI DllCanUnloadNow() {
    auto function = reinterpret_cast<DllCanUnloadNowFn>(
        ResolveReal("DllCanUnloadNow"));
    return function == nullptr ? S_FALSE : function();
}


extern "C" HRESULT WINAPI DllGetClassObject(
    REFCLSID class_id, REFIID interface_id, LPVOID* output) {
    auto function = reinterpret_cast<DllGetClassObjectFn>(
        ResolveReal("DllGetClassObject"));
    return function == nullptr
        ? CLASS_E_CLASSNOTAVAILABLE
        : function(class_id, interface_id, output);
}


extern "C" HRESULT WINAPI DllRegisterServer() {
    auto function = reinterpret_cast<DllRegisterServerFn>(
        ResolveReal("DllRegisterServer"));
    return function == nullptr ? E_FAIL : function();
}


extern "C" HRESULT WINAPI DllUnregisterServer() {
    auto function = reinterpret_cast<DllRegisterServerFn>(
        ResolveReal("DllUnregisterServer"));
    return function == nullptr ? E_FAIL : function();
}


extern "C" LPCDIDATAFORMAT WINAPI GetdfDIJoystick() {
    auto function = reinterpret_cast<GetdfDIJoystickFn>(
        ResolveReal("GetdfDIJoystick"));
    return function == nullptr ? nullptr : function();
}


BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = module;
        DisableThreadLibraryCalls(module);
        InstallChineseHooks();
    } else if (reason == DLL_PROCESS_DETACH && g_real_dinput8 != nullptr) {
        FreeLibrary(g_real_dinput8);
        g_real_dinput8 = nullptr;
    }
    return TRUE;
}
