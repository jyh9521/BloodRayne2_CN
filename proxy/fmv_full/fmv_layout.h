// Included inside the proxy's anonymous namespace. Only the FMV call site is
// redirected; menus, live dialogue and other languages keep their old layout.
#include "fmv_punctuation.h"

using FmvWrapFn = int(__thiscall*)(void*, const char*, char*, int, int, int);
FmvWrapFn g_original_fmv_wrap = nullptr;

struct FmvUnit {
    size_t offset;
    size_t bytes;
    float width;
    int punctuation; // 1: may not start a line; 2: may not end a line.
};

bool SplitFmvChinese(void* object, const char* text, char* output,
                     int max_lines, int stride, int max_width, int* line_count) {
    if (!object || !text || !output || !line_count || max_lines != 5 ||
        stride != 64 || max_width <= 0 || !IsChineseBitFont(object)) return false;
    const auto* glyphs = reinterpret_cast<const BitGlyphRecord*>(
        static_cast<const unsigned char*>(object)+4);
    float scale=0;
    memcpy(&scale,static_cast<const unsigned char*>(object)+0x2490,4);
    if (!(scale>0 && scale<100)) return false;
    const auto* input=reinterpret_cast<const unsigned char*>(text);
    const size_t length=strlen(text);
    if (length>1022) return false;
    std::vector<FmvUnit> units;
    bool found=false;
    for(size_t at=0;at<length;) {
        const unsigned char lead=input[at];
        const bool pair=at+1<length && lead>=0x81 && lead<=0x9F &&
                        input[at+1]>=0xA1 && input[at+1]<=0xFE;
        size_t count=pair?2:1;
        int kind=0;
        float width=static_cast<float>(glyphs[lead].width)*scale;
        if(pair) {
            found=true;
            const unsigned short code=static_cast<unsigned short>((lead<<8)|input[at+1]);
            kind=FmvPunctuation(code);
            width=static_cast<float>(kChineseGlyphWidth)*scale;
            if ((code==kFmvEllipsis || code==kFmvDash) && at+3<length &&
                input[at+2]==lead && input[at+3]==input[at+1]) {
                count=4;
                width*=2;
            }
        } else if(lead>=128) {
            return false; // Not a compiled Chinese string; preserve native path.
        }
        units.push_back({at,count,width,kind});
        at+=count;
    }
    if(!found) return false;
    std::vector<char> buffer(static_cast<size_t>(max_lines)*stride,0);
    size_t start=0;
    int rows=0;
    while(start<units.size() && rows<max_lines) {
        size_t end=start;
        size_t bytes=0;
        float width=0;
        while(end<units.size() && bytes+units[end].bytes<static_cast<size_t>(stride)
              && width+units[end].width<=static_cast<float>(max_width)) {
            bytes+=units[end].bytes;
            width+=units[end].width;
            ++end;
        }
        // Backtrack to the latest legal Chinese punctuation boundary.
        while(end>start && (units[end-1].punctuation==2 ||
              (end<units.size() && units[end].punctuation==1))) --end;
        if(end==start) return false;
        const size_t finish=units[end-1].offset+units[end-1].bytes;
        memcpy(buffer.data()+rows*stride,text+units[start].offset,
               finish-units[start].offset);
        ++rows;
        start=end;
    }
    if(start!=units.size()) return false;
    memcpy(output,buffer.data(),buffer.size());
    *line_count=rows;
    return true;
}

int __fastcall FmvChineseWrap(void* object, void*, const char* text,
                             char* output, int max_lines, int stride,
                             int max_width) {
    try {
        int rows=0;
        if(SplitFmvChinese(object,text,output,max_lines,stride,max_width,&rows))
            return rows;
    } catch(...) { }
    return g_original_fmv_wrap ?
        g_original_fmv_wrap(object,text,output,max_lines,stride,max_width) : 0;
}
