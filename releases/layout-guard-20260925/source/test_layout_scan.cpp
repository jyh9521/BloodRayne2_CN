#include <cstdio>
#include <cstring>

int main(int argc, char** argv) {
    const char* format = argc > 1 && std::strcmp(argv[1], "modified") == 0
        ? "@@%63[^@]@@%n" : "@@%[^@]@@%n";
    char long_tag[96] = "@@";
    std::memset(long_tag + 2, 'A', 80);
    std::memcpy(long_tag + 82, "@@", 3);
    char output[128];
    std::memset(output, 0x5A, sizeof(output));
    int consumed = -1;
    const int fields = std::sscanf(long_tag, format, output, &consumed);
    const bool canary = output[64] == 0x5A;
    char normal[128] = {};
    int normal_consumed = -1;
    const int normal_fields = std::sscanf("@@shootButtonName@@", format,
                                          normal, &normal_consumed);
    const bool normal_ok = normal_fields == 1 &&
        std::strcmp(normal, "shootButtonName") == 0 && normal_consumed == 19;
    std::printf("SCAN fields=%d canary=%s normal=%s consumed=%d\n",
                fields, canary ? "intact" : "overwritten",
                normal_ok ? "same" : "changed", consumed);
    return normal_ok && ((argc > 1 && std::strcmp(argv[1], "modified") == 0)
                            ? canary : !canary) ? 0 : 1;
}
