/* Minimal framebuffer shell for the RX 0.2 boot image. */
#include <fcntl.h>
#include <linux/fb.h>
#include <stdio.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

static void rect(unsigned char *pixels, int stride, int x, int y, int width, int height, unsigned int colour) {
    for (int row = y; row < y + height; ++row) {
        unsigned int *line = (unsigned int *)(pixels + row * stride);
        for (int column = x; column < x + width; ++column) line[column] = colour;
    }
}

int main(void) {
    int fb = open("/dev/fb0", O_RDWR);
    if (fb < 0) { puts("RX_SHELL=serial-fallback"); puts("RX_SESSION=ready"); return 0; }
    struct fb_var_screeninfo info;
    struct fb_fix_screeninfo fixed;
    if (ioctl(fb, FBIOGET_VSCREENINFO, &info) || ioctl(fb, FBIOGET_FSCREENINFO, &fixed) || info.bits_per_pixel != 32) {
        close(fb); puts("RX_SHELL=framebuffer-unavailable"); puts("RX_SESSION=ready"); return 0;
    }
    unsigned char *pixels = mmap(NULL, fixed.smem_len, PROT_READ | PROT_WRITE, MAP_SHARED, fb, 0);
    if (pixels == MAP_FAILED) { close(fb); puts("RX_SHELL=framebuffer-map-failed"); puts("RX_SESSION=ready"); return 0; }
    int width = info.xres, height = info.yres, stride = fixed.line_length;
    rect(pixels, stride, 0, 0, width, height, 0x00131b2d);
    rect(pixels, stride, 0, 0, width, 72, 0x00213a63);
    rect(pixels, stride, 28, 116, width - 56, height - 172, 0x001d2c45);
    rect(pixels, stride, 56, 148, 220, 126, 0x00425f9c);
    rect(pixels, stride, 304, 148, 220, 126, 0x00425f9c);
    rect(pixels, stride, 552, 148, 220, 126, 0x00425f9c);
    rect(pixels, stride, 56, height - 84, width - 112, 4, 0x004d7cfe);
    munmap(pixels, fixed.smem_len);
    close(fb);
    puts("RX_SHELL=framebuffer");
    puts("RX_SESSION=ready");
    return 0;
}
