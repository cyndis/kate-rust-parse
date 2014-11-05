# Rust error checking in Kate

Does live parse error checking and on-save compilation checking for Rust code using rustc.

When using Cargo, the Cargo primary target will be used for compilation checking. This script
doesn't actually use Cargo for building and doesn't build project dependencies, so please manually
build the project using Cargo first.
