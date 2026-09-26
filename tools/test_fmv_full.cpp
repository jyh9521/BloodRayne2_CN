// Independent diagnostic; no game loading, Bink playback, or graphics API.
#include "../proxy/fmv_full/dinput8_cn.cpp"
#include "../build/fmv_full_20260925/fixture_data.h"
#include <cstdio>
#include <cstdlib>

void require(bool ok,const char* message) {
    if(!ok) {std::printf("FAIL %s\n",message);std::exit(1);}
}
int __fastcall FakeNative(void*,void*,const char*,char*,int,int,int) {return 73;}

unsigned short code_at(const unsigned char* s) {
    if(s[0]>=0x81 && s[0]<=0x9F && s[1]>=0xA1 && s[1]<=0xFE)
        return static_cast<unsigned short>((s[0]<<8)|s[1]);
    return s[0];
}

int main() {
    std::vector<unsigned char> font(0x2500,0);
    strcpy(reinterpret_cast<char*>(font.data()+kBitFontNameOffset),"GOTHICTITLE_RU");
    auto* records=reinterpret_cast<BitGlyphRecord*>(font.data()+4);
    for(int i=0;i<256;++i) records[i].width=kFixtureWidths[i];
    const int screens[][2]={{640,480},{800,600},{1280,1024},{1920,1080},
                           {2560,1440},{3840,2160},{7680,4320}};
    int count=0,draw_count=0;
    for(const char* text:kFixtureCues) {
        for(const auto& screen:screens) {
            const float scale=screen[1]/480.0f*0.5f;
            memcpy(font.data()+0x2490,&scale,4);
            char output[400];memset(output,0x5A,sizeof(output));
            int rows=FmvChineseWrap(font.data(),nullptr,text,output,5,64,screen[0]);
            require(rows>0 && rows<=5,"row count or unexpected native fallback");
            for(size_t i=320;i<sizeof(output);++i) require(output[i]==0x5A,"buffer canary");
            std::string restored;
            for(int row=0;row<rows;++row) {
                auto* line=reinterpret_cast<unsigned char*>(output+64*row);
                require(strlen(reinterpret_cast<char*>(line))<64,"row terminated");
                if(row>0) require(FmvPunctuation(code_at(line))!=1,"closing punctuation at line start");
                unsigned short last=0;
                for(size_t i=0;line[i];) {
                    last=code_at(line+i);
                    if(line[i]>=128) {require(last>=0x81A1,"broken pair");i+=2;}
                    else ++i;
                }
                require(FmvPunctuation(last)!=2,"opening punctuation at line end");
                restored+=reinterpret_cast<char*>(line);
                std::vector<char> draw;
                require(PrepareDynamicText(font.data(),reinterpret_cast<char*>(line),&draw),"dynamic draw preparation");
                // Verify every transformed slot resolves to the original atlas
                // index, including the 62 new glyphs and repeated characters.
                size_t at=0;
                for(size_t i=0;line[i];) {
                    if(line[i]<128) {require(draw[at++]==line[i++],"ASCII preservation");continue;}
                    int index=(line[i]-0x81)*94+(line[i+1]-0xA1);
                    require(static_cast<unsigned char>(draw[at])==0x81,"carrier lead");
                    auto& record=records[static_cast<unsigned char>(draw[at+1])];
                    require(record.x==(index%kChineseAtlasColumns)*kChineseCellWidth &&
                            record.y==kChineseAtlasBaseY+(index/kChineseAtlasColumns)*kChineseRowPitch,"atlas address");
                    i+=2;at+=2;
                }
                ++draw_count;
            }
            require(restored==text,"no text loss during wrapping");
            ++count;
        }
    }
    g_original_fmv_wrap=reinterpret_cast<FmvWrapFn>(&FakeNative);
    char fallback[320]={};
    require(FmvChineseWrap(font.data(),nullptr,"English text",fallback,5,64,640)==73,"ASCII native fallback");
    strcpy(reinterpret_cast<char*>(font.data()+kBitFontNameOffset),"GOTHICTITLE_EN");
    require(FmvChineseWrap(font.data(),nullptr,kFixtureCues[0],fallback,5,64,640)==73,"foreign-font fallback");

    // Exercise the live patch writer against an isolated synthetic image.
    constexpr size_t site=0x28EB00,original=0xE5A90;
    auto* image=static_cast<unsigned char*>(VirtualAlloc(nullptr,site+0x1000,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE));
    require(image!=nullptr,"synthetic allocation");
    image[site]=0xE8;
    DWORD rel=static_cast<DWORD>(original-site-5);
    memcpy(image+site+1,&rel,4);
    require(PatchFmvWrapping(reinterpret_cast<HMODULE>(image)),"call-site patch");
    memcpy(&rel,image+site+1,4);
    DWORD destination=static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(image+site+5))+rel;
    require(destination==static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(&FmvChineseWrap)),"relocated E8 target");
    unsigned char saved[5];memcpy(saved,image+site,5);
    require(!PatchFmvWrapping(reinterpret_cast<HMODULE>(image)),"already patched signature guard");
    require(memcmp(saved,image+site,5)==0,"guard no-write");
    VirtualFree(image,0,MEM_RELEASE);
    std::printf("MODIFIED_PASS cues=%zu layout_cases=%d glyph_draws=%d pair_splits=0 text_loss=0 punctuation_orphans=0\n",sizeof(kFixtureCues)/sizeof(kFixtureCues[0]),count,draw_count);
    std::puts("PATCH_PASS E8_target=verified non_Chinese=native signature_guard=no_write game_launch=no");
    return 0;
}
