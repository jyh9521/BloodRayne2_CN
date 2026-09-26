// Standalone x86 diagnostic. Never loads or starts the game.
#ifndef CN_TEST_SOURCE
#define CN_TEST_SOURCE "../proxy/dinput8_cn.cpp"
#endif
#include CN_TEST_SOURCE
#include <cstdio>

int main() {
    constexpr size_t rva = 0xE6AB0;
    auto* base = static_cast<unsigned char*>(VirtualAlloc(
        nullptr, rva + 0x1000, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!base) return 2;
    // Synthetic thiscall function returns its last argument (shadow).
    const unsigned char code[] = {0x55,0x8B,0xEC,0x8B,0x45,0x18,0x5D,0xC2,0x14,0x00};
    memcpy(base+rva, code, sizeof(code));
    if (!PatchDynamicBitFontRenderer(reinterpret_cast<HMODULE>(base))) return 3;
    std::int32_t displacement=0;
    memcpy(&displacement,base+rva+1,4);
    const auto actual = reinterpret_cast<std::uintptr_t>(base+rva+5) + displacement;
    if (actual != reinterpret_cast<std::uintptr_t>(&DynamicBitFontDraw)) {
        std::puts("BASELINE_FAIL relocated E9 resolves to wrong destination; execution skipped");
        return 1;
    }
    std::vector<unsigned char> font(kBitFontNameOffset+64,0);
    strcpy(reinterpret_cast<char*>(font.data()+kBitFontNameOffset),"GOTHICTITLE_RU");
    const char carrier[] = {'A',char(0x82),char(0xA2),char(0x82),char(0xA2),0};
    std::vector<char> prepared;
    if (!PrepareDynamicText(font.data(),carrier,&prepared)) return 4;
    const char expected[]={'A',char(0x81),char(0xA1),char(0x81),char(0xA1),0};
    if (memcmp(prepared.data(),expected,sizeof(expected))) return 5;
    auto* glyphs=reinterpret_cast<BitGlyphRecord*>(font.data()+4);
    if (glyphs[0xA1].x!=(95%kChineseAtlasColumns)*kChineseCellWidth
        || glyphs[0xA1].width!=kChineseGlyphWidth) return 6;
    auto fn=reinterpret_cast<BitFontDrawFn>(base+rva);
    if (fn(font.data(),carrier,1,2,0xFFFFFF,73)!=73) return 7;
    strcpy(reinterpret_cast<char*>(font.data()+kBitFontNameOffset),"GOTHICTITLE_EN");
    if (fn(font.data(),"ASCII 123",1,2,0xFFFFFF,29)!=29) return 8;
    std::puts("MODIFIED_PASS E9 destination; executable trampoline; thiscall arguments; Chinese glyph slots; ASCII passthrough");
    VirtualFree(reinterpret_cast<void*>(g_original_bit_font_draw),0,MEM_RELEASE);
    VirtualFree(base,0,MEM_RELEASE);
    return 0;
}
