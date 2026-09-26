#include "dinput8_cn.cpp"
#include <cstdio>

int main() {
    EXCEPTION_RECORD record = {};
    CONTEXT context = {};
    EXCEPTION_POINTERS pair = {&record, &context};
    const auto* base = reinterpret_cast<const unsigned char*>(GetModuleHandleW(nullptr));
    record.ExceptionCode = EXCEPTION_ACCESS_VIOLATION;
    record.NumberParameters = 2;
    record.ExceptionInformation[0] = 0;
    record.ExceptionInformation[1] = 0xDEADBEEF;
    record.ExceptionAddress = const_cast<unsigned char*>(base + 0x1DE9B0);
    context.Eip = static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(record.ExceptionAddress));
    context.Ebx = 0xDEADBEEF;
    const LONG recovered = RecoverLayoutReadFault(&pair);
    const bool cursor_safe = context.Ebx ==
        static_cast<DWORD>(reinterpret_cast<ULONG_PTR>(kEmptyLayoutText));
    std::printf("RECOVERY pc=005DE9B0 result=%ld cursor=%s faults=%ld\n",
        recovered, cursor_safe ? "empty" : "bad", g_layout_fault_count);
    record.ExceptionAddress = const_cast<unsigned char*>(base + 0x1DE9B1);
    context.Ebx = 0xDEADBEEF;
    const LONG unrelated = RecoverLayoutReadFault(&pair);
    std::printf("UNRELATED result=%ld cursor=%s\n", unrelated,
        context.Ebx == 0xDEADBEEF ? "unchanged" : "changed");
    return recovered == EXCEPTION_CONTINUE_EXECUTION && cursor_safe &&
        unrelated == EXCEPTION_CONTINUE_SEARCH && context.Ebx == 0xDEADBEEF
        ? 0 : 1;
}
