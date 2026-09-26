inline int FmvPunctuation(unsigned short code) {
    switch(code) {
    case 0x93BF: return 1;
    case 0x81A7: return 1;
    case 0x81A6: return 1;
    case 0x93BC: return 1;
    case 0x93C1: return 1;
    case 0x93C0: return 1;
    case 0x93BE: return 1;
    case 0x81A9: return 1;
    case 0x81A4: return 1;
    case 0x93BD: return 2;
    case 0x81A8: return 2;
    case 0x81A3: return 2;
    default: return 0;
    }
}
constexpr unsigned short kFmvEllipsis=0x81A5;
constexpr unsigned short kFmvDash=0x81A2;
