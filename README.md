# png

A PNG reader for [sysl](https://github.com/sysl-lang/sysl), and the DEFLATE decoder underneath it.

Bytes go in and an `Image` comes out, with the chunk layer, both checksums, the deflate stream and
the row filters done on the way. All five colour types are read at eight bits a sample, and
`at(x, y)` answers an `Rgba` whichever of them the file used — so a caller drawing an image never
finds out which one it was.

Nothing here is a design of ours to get right, which is the whole character of the package: the
signature is eight specific bytes, the chunk lengths are big-endian, the bit stream inside them is
little-endian, the Huffman codes inside *that* are packed the other way up again, the filters are
modulo 256, and the two checksums are computed by two unrelated methods. A reader that gets any of it
wrong still produces an image; it just produces the wrong one.

```
sh/sysl/png/
    png.sysl            the chunks, the checksum, the filters, and the pixels underneath
    inflate/
        inflate.sysl    DEFLATE and the zlib wrapper — its own format, and reachable on its own
    tests.sysl          what all of it claims, run by `sysl test .`
package.hocon           who this package is, and what it needs of the machine
```

The modules are **`sh.sysl.png`** and **`sh.sysl.png.inflate`**, and the directories are those names:
a dotted module name mirrors its path from the library root. The prefix is the reverse-DNS of
`sysl.sh`, so that a package claims a name nobody else will mint rather than the top-level word
`png`.

## Using it

Name it in your project's `package.hocon` and `sysl build` fetches it:

```hocon
dependencies {
  png { git = "github.com/sysl-lang/png", version = "0.1.1" }
}
```

```sysl
import sh.sysl.png.{decode, describe}

decode(bytes) match
    Err(f) -> print(s"not readable: $f")
    Ok(img) ->
        print(s"${str(img.width)}x${str(img.height)}")

        val p = img.at(0, 0)

        print(s"${str(p.r)} ${str(p.g)} ${str(p.b)} ${str(p.a)}")
```

`decode` takes the file's bytes and nothing else — where they came from is your program's business,
and this package opens nothing. It sizes its own two intermediate buffers, so there is no storage
argument and no fault meaning "your buffer was too small".

**An `Image` views the bytes it was decoded from.** `palette` is a slice of the source rather than a
copy, which is why an image may not outlive the file it came from — and why nothing has to say so,
since a slice retains what it views. `raw` is storage of its own: the unpacked rows, still carrying
the spent filter byte at the head of each, because leaving it there costs one addition per row and
saves copying the whole image to remove it.

## What it will not read

Sixteen bits a sample, and interlaced images. Both are refused by name rather than read wrongly:
`BadDepth(16)` and `Interlaced`. A chunk that is critical and unknown is refused too, which is what
the format asks of a reader; an ancillary one is walked past.

Every refusal is a variant of `Fault` with the position or the value in it, so a caller can say
*where* and *what* rather than "this file is broken". A `Fault` renders as its own sentence, so
`s"$f"` is the message; `describe(f)` is the same sentence as a value, for a caller assembling a
diagnostic of its own.

## DEFLATE on its own

`sh.sysl.png.inflate` has nothing to do with pictures — a bit stream with its own errors, its own
checksum, and no opinion about what the bytes it produces mean:

```sysl
import sh.sysl.png.inflate

inflate.zlib(compressed, out) match
    Ok(n) -> print(s"${str(n)} bytes")
    Err(f) -> print(s"$f")
```

`zlib` reads the wrapper and checks the Adler-32; `raw` reads a bare deflate stream and checks
nothing, which is the only way to ask what the decoder does with bits no encoder would have written.
Both write into storage the caller supplies and answer how many bytes they wrote, so this half needs
no allocator of its own.

## On a microcontroller

**It builds for a freestanding target**, which is not free and is the one thing about this package
worth knowing before depending on it. The CRC table is *derived* rather than written down, and a
module-level `val` holding a derived value is storage an initializer has to fill before anything
else runs — which a `build-c` archive has no entry point to do and a freestanding target has no
loader to do either. So the table is a value:

```sysl
val crc = crc32_table()

crc.of(chunk)
```

`crc32(data)` is still there for one-shot use and builds a table each call. `decode` builds one per
file rather than one per chunk.

Checked rather than assumed — an `@export`ed function calling `decode`, built with

```
sysl build-c <program> --target thumb-freestanding-softfp
```

**There is no test for that**, and there cannot be: `sysl test .` runs on the host, where module
storage is filled before any export can run, so a host suite is green on a package that cannot be put
on a board at all. Run the command above in the loop of any change that adds a module-level binding.

What the *decoder* needs of the machine is a heap, and that is `requires { heap = true }` in the
manifest: `decode` gathers the `IDAT` chunks into one buffer and unpacks them into another, and
neither length is known until the header has been read — which happens inside. The `inflate` half
needs nothing.

## Testing it

```
sysl test .
```

17 tests, and **every value they compare was computed by somebody else**. The fixtures came out of a
different encoder than the one that reads them, which is the only reason any of this proves anything:
a decoder tested against its own encoder tests that two mistakes agree. The checksum vectors are the
published ones. Every image is written out in hex in `tests.sysl` and unpacked at the start of each
check, so nothing opens a file.

The strongest single check is the picture: an eight-by-eight checkerboard decoded and printed as `#`
and `.`, compared against the pattern that generated it. A filter undone wrongly, or a row read at
the wrong offset, shows up there in a way no assertion about a byte would.

## Where it came from

It was `guide/png` in the compiler's own repository — one of the programs written to force a language
decision rather than to demonstrate a finished language. The byte level was its axis, and what it
found is in the language now: the multi-line text block, whose lines join at a trailing backslash
(this package's fixtures are ten of them); the separation between a table the format writes down and
a table you have to derive; and a decoder's intermediate storage coming out of its signature. Its
findings discharged, it is a package rather than a lesson.

## License

ISC — see [LICENSE](LICENSE).
