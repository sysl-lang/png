# png

A PNG reader and writer for [sysl](https://github.com/sysl-lang/sysl), and the DEFLATE decoder and
compressor underneath them — all of it sysl, with no C and no zlib.

Bytes go in and an `Image` comes out, with the chunk layer, both checksums, the deflate stream, the
row filters and the interlacing done on the way; an `Image` goes back out as a file the same way
round. Every colour type is read and written at every depth the format allows it, and `at(x, y)`
answers an `Rgba` whichever of them the file used — so a caller drawing an image never finds out
which one it was.

Nothing here is a design of ours to get right, which is the whole character of the package: the
signature is eight specific bytes, the chunk lengths are big-endian, the bit stream inside them is
little-endian, the Huffman codes inside *that* are packed the other way up again, the filters are
modulo 256, and the two checksums are computed by two unrelated methods. A reader that gets any of it
wrong still produces an image; it just produces the wrong one.

```
sh/sysl/png/
    png.sysl            the reader: chunks, checksum, filters, interlacing, pixels, animation
    write.sysl          the writer: filtering, interlacing, chunks
    inflate/
        inflate.sysl    DEFLATE and the zlib wrapper, decoded — its own format, reachable on its own
    deflate/
        deflate.sysl    DEFLATE and the zlib wrapper, compressed — reachable on its own too
    *tests.sysl         what all of it claims, run by `sysl test .`
testdata/
    pngsuite/           PngSuite, the format's conformance images
    apng/               two animations, and the script that wrote them
sysl.hocon              who this package is, and what it needs of the machine
```

The modules are **`sh.sysl.png`**, **`sh.sysl.png.inflate`** and **`sh.sysl.png.deflate`**, and the
directories are those names: a dotted module name mirrors its path from the library root.

## Using it

Name it in your project's `sysl.hocon` and `sysl build` fetches it:

```hocon
dependencies {
  png { git = "github.com/sysl-lang/png", version = "0.2.0" }
}
```

```sysl
import sh.sysl.png.{decode, encode, options}

decode(bytes) match
    Err(f) -> print(s"not readable: $f")
    Ok(img) ->
        print(s"${img.width.to_string()}x${img.height.to_string()}, type ${img.kind.to_string()}, ${img.depth.to_string()} bits")

        val p = img.at(0, 0)

        print(s"${p.r.to_string()} ${p.g.to_string()} ${p.b.to_string()} ${p.a.to_string()}")

        var o = options()

        o.level = 9
        o.interlaced = true

        val file = encode(img, o).unwrap()
```

`decode` takes the file's bytes and nothing else — where they came from is your program's business,
and this package opens nothing. `encode` answers the file's bytes in a `Buf[u8]`.

### What an `Image` is

| field | holds |
|---|---|
| `width`, `height`, `kind`, `depth` | the header: colour type 0, 2, 3, 4 or 6, and 1, 2, 4, 8 or 16 bits a sample |
| `data` | the pixels as the file's own samples, whole rows of `row_bytes()`: narrow samples packed from the top bit, 16-bit ones big-endian — with the filter bytes gone and the interlacing undone |
| `interlaced` | only how the file stored it |
| `palette`, `alpha` | the palette as RGB triples, and the opacity of its first entries from `tRNS` |
| `keyed`, `key` | a grey or truecolour `tRNS`: the one colour that is transparent |
| `info` | `gamma`, `srgb`, `profile` (an ICC profile, unpacked), `phys`, and `texts` — every `tEXt`, `zTXt` and `iTXt`, as UTF-8 |

Three ways to read a pixel: `sample(x, y, c)` is a sample exactly as stored; `at16(x, y)` is
`Rgba16`, every depth scaled to sixteen bits by repeating its bits, a palette looked up and the
transparency applied; `at(x, y)` is `Rgba`, the high byte of each of those.

**An `Image` views the bytes it was decoded from.** `palette` and `alpha` are slices of the source
rather than copies, which is why an image may not outlive the file it came from — and why nothing has
to say so, since a slice retains what it views.

### Writing

An `Image` from `decode` writes back with its palette, transparency and ancillary chunks. One made
from raw rows starts with `image(width, height, kind, depth, data)`, which checks the rows are the
size the header says, and then has a palette, transparency or `info` set on it:

```sysl
var img = image(64, 64, 3, 4, rows).unwrap()

img.palette = colours
img.info.texts.push(Text("Title", "Café", false, false, "", ""))

val file = encode(img).unwrap()
```

`Options` is `level` (0–9, the deflate level), `filter`, `interlaced` and `chunk`, the most image
data one `IDAT` carries (64 KB by default). The filter is `Nothing`, `Sub`, `Up`, `Average`, `Paeth`
on every row, or `Adaptive` — the default — which tries all five on each row and keeps the one whose
bytes, read as signed, sum smallest: the heuristic the specification recommends, and its other
recommendation too, no filtering at all for a palette or samples narrower than a byte.

An image no file could hold is refused before a byte is written: a depth the colour type does not
have, rows of the wrong size, a palette index past the palette, a transparent colour wider than a
sample, a keyword or Latin-1 text that is not one, an sRGB chunk beside a profile.

### Animation

`decode` reads an animated PNG as its default image, which is what it was designed to look like to a
reader that knows nothing of animation. `decode_animation` reads it as an `Animation`: the default
image, `frames` — each an `Image` with its offset on the canvas, its delay as a fraction of a second,
and how it is disposed of and blended — `plays` (zero for ever), and whether the default image is the
first frame. Sequence numbers, the promised frame count and every frame's place on the canvas are
checked.

### What it will not do

**Decode incrementally.** `decode` takes the whole file. A streaming decoder needs an inflater that
can stop mid-symbol and resume when more bytes arrive, and the decoder here is a loop over a buffer
that is all there; bolting resumption on would change both halves of its API, so it is not here.

**Write an animation**, or the ancillary chunks it reads past — `cHRM`, `sBIT`, `bKGD`, `hIST`,
`sPLT`, `tIME`, `eXIf`. A critical chunk it does not know is refused, which is what the format asks
of a reader; an ancillary one is walked past.

Every refusal is a variant of `Fault` with the position or the value in it, so a caller can say
*where* and *what* rather than "this file is broken". A `Fault` renders as its own sentence, so
`s"$f"` is the message; `describe(f)` is the same sentence as a value.

## DEFLATE on its own

`sh.sysl.png.inflate` and `sh.sysl.png.deflate` have nothing to do with pictures:

```sysl
import sh.sysl.png.{deflate, inflate}

val z = deflate.zlib(bytes, 9)

inflate.zlib(z.view(), out) match
    Ok(n) -> print(s"${n.to_string()} bytes")
    Err(f) -> print(s"$f")
```

`deflate.zlib` and `deflate.compress` (bare, no wrapper) take a level from 0 to 9 meaning roughly
what zlib's do: **0** stores; **1–3** match greedily over the 32 KB window with short hash chains;
**4–9** match lazily — a match is held while the next position is tried, and loses to a longer one
there — with chains growing to 4,096 links at 9. Each block is costed stored, under the fixed code
and under a dynamic code of its own, and written the cheapest way; `Blocks.Fixed` or
`Blocks.Dynamic` forces one. The dynamic codes are length-limited — 15 bits, and 7 for the code
lengths' own code — by building the optimal code and repairing the lengths over the limit in a way
that provably fills the tree exactly.

`inflate.zlib` checks the wrapper and the Adler-32; `inflate.raw` reads a bare stream. Both write
into storage the caller supplies and answer how many bytes they wrote; `inflate.zlib_any` sizes its
own, growing up to a limit, for a stream whose size nobody wrote down.

## Speed

Measured on an M-series Mac against zlib (python3's `zlib`, which is the C library) on the same
inputs, MB/s of input, three rounds each; the program was built at `optimization = "2"`.

| input | level | compress, ours | compress, zlib | decompress, ours | decompress, zlib |
|---|---|---|---|---|---|
| 2.5 MB of English text | 1 | 134 | 164 | 343 | 1137 |
| | 6 | 33 | 42 | 421 | 1285 |
| | 9 | 25 | 33 | 419 | 1272 |
| 3.1 MB of filtered RGB rows | 1 | 102 | 174 | 290 | 840 |
| | 6 | 21 | 34 | 341 | 747 |
| | 9 | 21 | 34 | 340 | 709 |

Compression is 1.2–1.3× zlib's time on text and 1.6–1.7× on picture rows; decompression is 2.2–3.3×.
Sizes are zlib's to within a percent from level 4 up, and 5.5% larger at worst (a filtered picture
at level 3, where zlib runs a different, faster loop).

**Where the time goes.** Compression spends nine tenths of it in the match search, as zlib does.
Decompression is table-driven — one lookup for any code of ten bits or fewer — and spends its time in
that loop, the match copies and the Adler-32. **Bounds checks are not the difference**: the compare
loop of the match search and the literal store and copy of the decoder, rewritten with unchecked
`*T` access as an experiment, ran no faster. What zlib has that this does not is hand-tuning — word-
at-a-time match copies and comparisons and, in the build python links, a vectorised Adler-32.

## On a microcontroller

**It builds for a freestanding target.** The CRC table is *derived* rather than written down, and a
module-level `val` holding a derived value is storage an initializer has to fill before anything
else runs — which a `build-c` archive has no entry point to do and a freestanding target has no
loader to do either. So the table is a value, built by whoever wants it:

```sysl
val crc = crc32_table()

crc.of(chunk)
```

The compressor's length and distance tables are built per call for the same reason. Checked with an
`@export`ed function calling `decode`, `encode` and `deflate.zlib`, built with

```
sysl build-c <program> --target thumb-freestanding-softfp
```

**There is no test for that**, and there cannot be: `sysl test .` runs on the host, where module
storage is filled before any export can run. Run the command above in the loop of any change that
adds a module-level binding. What the package needs of the machine is a heap — `requires { heap =
true }` — and `inflate` alone needs nothing.

## Testing it

```
sysl test .
```

46 tests, and **the answers they check come from somebody else**:

- **PngSuite** (below): all 162 valid images decode to exactly the pixels **stb_image** makes of them,
  compared at sixteen bits and at eight, and all 14 broken ones are refused, each with the sentence
  its breakage deserves. stb is the org's binding, a `dev_dependency`, so a consumer never fetches it.
- **The writer**: every colour type at every depth, with and without transparency, interlaced and
  not, at three sizes — 180 files — reads back to the same samples, reads through stb to the same
  RGBA, and passes **`pngcheck -v`**. So does every PngSuite image re-encoded, plain and interlaced,
  324 more.
- **The compressor**: eleven inputs — text, noise, zeros, empty, one byte, 32 KB and 64 KB either
  side, runs around the match limits, a picture's filtered rows — at every level and every block
  kind, inflated by **zlib itself** (python3's `zlib`) back to what went in, 330 streams, with the
  sizes held within 10% of zlib's at the same level. Five hundred random inputs round-trip besides.
- **Error paths**: a bad checksum, a stream cut short, a wrong Adler-32, a filter byte past 4, chunks
  out of order, ancillary chunks of the wrong size, animations out of sequence — each with its exact
  error.

The suite runs `pngcheck` and `python3`, which have to be on the path. Under AddressSanitizer —
`SYSL_EXTRA_CFLAGS="-fsanitize=address -g" sysl test .` — it is clean.

### PngSuite

`testdata/pngsuite/` is Willem van Schaik's PngSuite, release 2017-07-19, as downloaded from
<http://www.schaik.com/pngsuite/PngSuite-2017jul19.tgz> (SHA-256
`0294b244c95a8342c01b00010cf34abdcabc7c6a34fd0fe1bd963917537bfdc8`), unpacked unchanged, with its
licence beside it: free to use, copy and distribute.

`testdata/apng/` holds two animations written by `mkapng.py` beside them — by hand, with python's
`zlib` — so the animation reader is checked against an encoder that is not this package's.

## Where it came from

It was `guide/png` in the compiler's own repository — one of the programs written to force a language
decision rather than to demonstrate a finished language. The byte level was its axis, and what it
found is in the language now: the multi-line text block, whose lines join at a trailing backslash;
the separation between a table the format writes down and a table you have to derive; and a
decoder's intermediate storage coming out of its signature. The writer and the compressor were the
org's first hot bit-twiddling encoder loops in sysl.

## License

ISC — see [LICENSE](LICENSE).
