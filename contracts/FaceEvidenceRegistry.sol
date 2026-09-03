// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title  FaceEvidenceRegistry
/// @notice Tamper-evident anchor for face-identification evidence bundles.
/// @dev    PRIVACY INVARIANT: this contract stores only irreversible digests.
///         No embedding, no image, no PII is ever written on chain. The
///         embedding is quantized to int8 and SHA-256'd off chain; only that
///         digest arrives here.
contract FaceEvidenceRegistry {
    struct Record {
        bytes32 evidenceHash;   // sha256 of the canonical evidence JSON
        bytes32 pHash;          // 64-bit perceptual hash of the matched image
        bytes32 embeddingHash;  // sha256 of the int8-quantized ArcFace vector
        bytes32 merkleRoot;     // non-zero only for batch anchors
        uint64  timestamp;      // block time of the FIRST anchor
        uint32  itemCount;      // 1 for a single record, N for a batch
        address submitter;
        string  cid;            // optional IPFS CID of the full bundle
    }

    Record[] private _records;

    /// @dev evidenceHash => id + 1. Zero means "absent", which lets id 0 exist.
    mapping(bytes32 => uint256) private _indexOf;
    /// @dev merkleRoot => id + 1.
    mapping(bytes32 => uint256) private _rootIndex;

    event EvidenceAnchored(
        uint256 indexed id,
        bytes32 indexed evidenceHash,
        bytes32 indexed merkleRoot,
        address submitter,
        uint64  timestamp,
        uint32  itemCount
    );

    error AlreadyAnchored(uint256 existingId, uint64 firstSeen);
    error EmptyHash();
    error NotFound();

    // ------------------------------------------------------------- writes

    /// @notice Anchor a single evidence bundle.
    /// @dev Reverts if this hash was already anchored. That is deliberate: the
    ///      FIRST anchor timestamp is the entire evidentiary claim, and letting
    ///      anyone overwrite it would defeat the purpose of the registry.
    function anchor(
        bytes32 evidenceHash,
        bytes32 pHash,
        bytes32 embeddingHash,
        string calldata cid
    ) external returns (uint256 id) {
        if (evidenceHash == bytes32(0)) revert EmptyHash();

        uint256 existing = _indexOf[evidenceHash];
        if (existing != 0) {
            revert AlreadyAnchored(existing - 1, _records[existing - 1].timestamp);
        }

        id = _records.length;
        _records.push(Record({
            evidenceHash:  evidenceHash,
            pHash:         pHash,
            embeddingHash: embeddingHash,
            merkleRoot:    bytes32(0),
            timestamp:     uint64(block.timestamp),
            itemCount:     1,
            submitter:     msg.sender,
            cid:           cid
        }));
        _indexOf[evidenceHash] = id + 1;

        emit EvidenceAnchored(
            id, evidenceHash, bytes32(0), msg.sender, uint64(block.timestamp), 1
        );
    }

    /// @notice Anchor N bundles in ONE transaction via a Merkle root.
    /// @dev Gas is O(1) in the number of records. Individual membership is
    ///      proved later with verifyInclusion().
    function anchorBatch(
        bytes32 merkleRoot,
        uint32  itemCount,
        string calldata cid
    ) external returns (uint256 id) {
        if (merkleRoot == bytes32(0)) revert EmptyHash();

        uint256 existing = _rootIndex[merkleRoot];
        if (existing != 0) {
            revert AlreadyAnchored(existing - 1, _records[existing - 1].timestamp);
        }

        id = _records.length;
        _records.push(Record({
            evidenceHash:  bytes32(0),
            pHash:         bytes32(0),
            embeddingHash: bytes32(0),
            merkleRoot:    merkleRoot,
            timestamp:     uint64(block.timestamp),
            itemCount:     itemCount,
            submitter:     msg.sender,
            cid:           cid
        }));
        _rootIndex[merkleRoot] = id + 1;

        emit EvidenceAnchored(
            id, bytes32(0), merkleRoot, msg.sender, uint64(block.timestamp), itemCount
        );
    }

    // -------------------------------------------------------------- reads

    function verify(bytes32 evidenceHash)
        external
        view
        returns (bool found, Record memory record)
    {
        uint256 i = _indexOf[evidenceHash];
        if (i == 0) return (false, record);
        return (true, _records[i - 1]);
    }

    /// @notice Prove a leaf belongs to a Merkle root that was anchored here.
    /// @dev Sorted-pair hashing: the smaller sibling is hashed first, so a
    ///      proof needs no left/right position bits. faceproof/merkle.py builds
    ///      proofs with the identical rule.
    function verifyInclusion(
        bytes32 root,
        bytes32 leaf,
        bytes32[] calldata proof
    ) external view returns (bool) {
        if (_rootIndex[root] == 0) return false;

        bytes32 h = leaf;
        for (uint256 i = 0; i < proof.length; ++i) {
            bytes32 p = proof[i];
            h = h <= p
                ? keccak256(abi.encodePacked(h, p))
                : keccak256(abi.encodePacked(p, h));
        }
        return h == root;
    }

    function isAnchored(bytes32 evidenceHash) external view returns (bool) {
        return _indexOf[evidenceHash] != 0;
    }

    function rootAnchored(bytes32 merkleRoot) external view returns (bool) {
        return _rootIndex[merkleRoot] != 0;
    }

    function recordCount() external view returns (uint256) {
        return _records.length;
    }

    function recordAt(uint256 id) external view returns (Record memory) {
        if (id >= _records.length) revert NotFound();
        return _records[id];
    }
}
