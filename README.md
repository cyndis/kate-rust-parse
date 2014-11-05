# Rust error checking in Kate

Does live parse error checking and on-save compilation checking for Rust code using rustc.

The crate root is not detected, so compilation checking while editing other files will be wrong.
Cargo is also not supported (it doesn't have a way to pass --no-trans).

