#include <windows.h>
#include <cstdio>

int main() {
    volatile const char* invalid = reinterpret_cast<volatile const char*>(0xDEADBEEF);
    DWORD code = 0;
    __try {
        volatile char value = *invalid;
        (void)value;
    } __except (code = GetExceptionCode(), EXCEPTION_EXECUTE_HANDLER) {
        std::printf("BASELINE_FAULT code=%08lX cursor=DEADBEEF recovery=none\n", code);
    }
    return code == EXCEPTION_ACCESS_VIOLATION ? 0 : 1;
}
