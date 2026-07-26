/* Known-plaintext trajectory search against the autonomous cascade.
 *
 * The autonomous machine's state at time t is (c0 + t mod A, d0 + t mod B).
 * The attack enumerates the pair (c0, d0) -- the whole state space -- and for
 * each hypothesis undoes the two stages to obtain the reduced stream
 *
 *     z_t = rho^{-1}_{c0+t} ( sigma^{-1}_{d0+t} ( y_t ) ) ,
 *
 * which under the correct hypothesis equals P(x_t).  The plugboard P is never
 * searched: it is read off, and its only role is to supply a consistency test
 * (a partial involution with at most `pairs` transpositions).  The program
 * reports, for every candidate, the longest crib prefix it survives, which
 * yields both the survivor curve and the unicity distance.
 *
 * Build: gcc -O3 -march=native -fopenmp -o violet_attack violet_attack.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <omp.h>

typedef struct {
    int n, r, k, A, B, L, pairs;
    unsigned char *rho_inv;  /* A x n */
    unsigned char *sig_inv;  /* B x n */
    unsigned char *x, *y;    /* crib */
} Problem;

/* Longest crib prefix that hypothesis (c0,d0) survives. */
static inline int survive_len(const Problem *p, int c0, int d0)
{
    unsigned char map[64];
    memset(map, 0xFF, sizeof(map));
    const int n = p->n, maxfix = p->n - 2 * p->pairs;
    int used = 0, fixed = 0, c = c0, d = d0;
    for (int t = 0; t < p->L; ++t) {
        const int z = p->rho_inv[(size_t)c * n + p->sig_inv[(size_t)d * n + p->y[t]]];
        const int a = p->x[t];
        if (map[a] != 0xFF) {
            if (map[a] != z) return t;              /* contradicts an earlier reading */
        } else if (map[z] != 0xFF) {
            return t;                               /* z is already taken by another letter */
        } else if (a == z) {
            if (fixed + 1 > maxfix) return t;       /* too many unplugged letters */
            fixed++;
            map[a] = (unsigned char)z;
        } else {
            if (used + 1 > p->pairs) return t;      /* too many transpositions */
            used++;
            map[a] = (unsigned char)z;
            map[z] = (unsigned char)a;
        }
        if (++c == p->A) c = 0;
        if (++d == p->B) d = 0;
    }
    return p->L;
}

int main(int argc, char **argv)
{
    if (argc < 3) { fprintf(stderr, "usage: %s spec.bin out.bin\n", argv[0]); return 1; }
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror("open"); return 1; }
    int hdr[7];
    if (fread(hdr, sizeof(int), 7, f) != 7) { fprintf(stderr, "bad header\n"); return 1; }
    Problem p;
    p.n = hdr[0]; p.r = hdr[1]; p.k = hdr[2];
    p.A = hdr[3]; p.B = hdr[4]; p.L = hdr[5]; p.pairs = hdr[6];
    p.rho_inv = malloc((size_t)p.A * p.n);
    p.sig_inv = malloc((size_t)p.B * p.n);
    p.x = malloc(p.L); p.y = malloc(p.L);
    if (fread(p.rho_inv, 1, (size_t)p.A * p.n, f) != (size_t)p.A * p.n) return 1;
    if (fread(p.sig_inv, 1, (size_t)p.B * p.n, f) != (size_t)p.B * p.n) return 1;
    if (fread(p.x, 1, p.L, f) != (size_t)p.L) return 1;
    if (fread(p.y, 1, p.L, f) != (size_t)p.L) return 1;
    fclose(f);

    long long total = (long long)p.A * p.B;
    long long *hist = calloc(p.L + 1, sizeof(long long));
    double t0 = omp_get_wtime();

    #pragma omp parallel
    {
        long long *local = calloc(p.L + 1, sizeof(long long));
        #pragma omp for schedule(static)
        for (long long idx = 0; idx < total; ++idx) {
            const int c0 = (int)(idx / p.B);
            const int d0 = (int)(idx % p.B);
            local[survive_len(&p, c0, d0)]++;
        }
        #pragma omp critical
        for (int i = 0; i <= p.L; ++i) hist[i] += local[i];
        free(local);
    }
    double elapsed = omp_get_wtime() - t0;

    FILE *g = fopen(argv[2], "wb");
    fwrite(&total, sizeof(long long), 1, g);
    fwrite(&elapsed, sizeof(double), 1, g);
    fwrite(hist, sizeof(long long), p.L + 1, g);
    fclose(g);
    fprintf(stderr, "candidates=%lld  seconds=%.3f  rate=%.2f M/s  full-survivors=%lld\n",
            total, elapsed, total / elapsed / 1e6, hist[p.L]);
    return 0;
}
