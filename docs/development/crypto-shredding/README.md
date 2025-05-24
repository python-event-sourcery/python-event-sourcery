# Feature: Privacy data

## General idea
I want to implement feature that gives an easy way to reject access to all data marked as private data. It's inspired by
blogpost https://www.kurrent.io/blog/protecting-sensitive-data-in-event-sourced-systems-with-crypto-shredding-1

Use-case it to provide API in our library that allows to encrypt marked fields on events, and a way to fast mark that
access to this data was rejects. This should remove encription keys that allows access to this data.

- [x] [ADR-0009: Privacy Data Encryption and Crypto-Shredding](../../docs/adr/0009-privacy-data-encryption-and-shredding.md)
- [x] [Design](design.md)
- [ ] [Tests](tests.md)
