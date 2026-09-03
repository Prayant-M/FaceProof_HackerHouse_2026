const { expect } = require("chai");
const { ethers } = require("hardhat");
const { anyUint } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

const h = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));
const ZERO = ethers.ZeroHash;

// sorted-pair hashing -- must match faceproof/merkle.py and the contract
const pair = (a, b) =>
  a.toLowerCase() <= b.toLowerCase()
    ? ethers.keccak256(ethers.concat([a, b]))
    : ethers.keccak256(ethers.concat([b, a]));

function buildTree(leaves) {
  const levels = [leaves.slice()];
  while (levels[levels.length - 1].length > 1) {
    const cur = levels[levels.length - 1];
    const next = [];
    for (let i = 0; i < cur.length; i += 2) {
      next.push(i + 1 < cur.length ? pair(cur[i], cur[i + 1]) : cur[i]);
    }
    levels.push(next);
  }
  return { root: levels[levels.length - 1][0], levels };
}

function proofFor(levels, index) {
  const out = [];
  for (let l = 0; l < levels.length - 1; l++) {
    const sib = index ^ 1;
    if (sib < levels[l].length) out.push(levels[l][sib]);
    index = Math.floor(index / 2);
  }
  return out;
}

describe("FaceEvidenceRegistry", function () {
  let reg, owner;

  beforeEach(async function () {
    [owner] = await ethers.getSigners();
    const F = await ethers.getContractFactory("FaceEvidenceRegistry");
    reg = await F.deploy();
    await reg.waitForDeployment();
  });

  it("anchors a record and reads it back", async function () {
    const ev = h("evidence-1");
    await reg.anchor(ev, h("phash"), h("emb"), "");
    const [found, rec] = await reg.verify(ev);
    expect(found).to.equal(true);
    expect(rec.evidenceHash).to.equal(ev);
    expect(rec.submitter).to.equal(owner.address);
    expect(rec.itemCount).to.equal(1);
  });

  it("reports not-found for an unknown hash", async function () {
    const [found] = await reg.verify(h("never-anchored"));
    expect(found).to.equal(false);
  });

  it("refuses to overwrite a first-seen timestamp", async function () {
    const ev = h("evidence-1");
    await reg.anchor(ev, h("p"), h("e"), "");
    await expect(reg.anchor(ev, h("p2"), h("e2"), "")).to.be.revertedWithCustomError(
      reg,
      "AlreadyAnchored"
    );
  });

  it("rejects an empty evidence hash", async function () {
    await expect(reg.anchor(ZERO, h("p"), h("e"), "")).to.be.revertedWithCustomError(
      reg,
      "EmptyHash"
    );
  });

  it("emits EvidenceAnchored", async function () {
    const ev = h("evidence-emit");
    await expect(reg.anchor(ev, h("p"), h("e"), "ipfs://cid"))
      .to.emit(reg, "EvidenceAnchored")
      .withArgs(0, ev, ZERO, owner.address, anyUint, 1);
  });

  it("verifies Merkle inclusion for every leaf in a batch", async function () {
    const leaves = [...Array(5).keys()].map((i) => h(`leaf-${i}`));
    const { root, levels } = buildTree(leaves);
    await reg.anchorBatch(root, leaves.length, "");

    for (let i = 0; i < leaves.length; i++) {
      expect(await reg.verifyInclusion(root, leaves[i], proofFor(levels, i))).to.equal(
        true,
        `leaf ${i}`
      );
    }
  });

  it("rejects inclusion against an unanchored root", async function () {
    const leaves = [h("a"), h("b")];
    const { root, levels } = buildTree(leaves);
    expect(await reg.verifyInclusion(root, leaves[0], proofFor(levels, 0))).to.equal(false);
  });

  it("rejects a forged leaf", async function () {
    const leaves = [h("a"), h("b"), h("c")];
    const { root, levels } = buildTree(leaves);
    await reg.anchorBatch(root, 3, "");
    expect(await reg.verifyInclusion(root, h("forged"), proofFor(levels, 0))).to.equal(false);
  });

  it("counts records", async function () {
    await reg.anchor(h("one"), h("p"), h("e"), "");
    await reg.anchor(h("two"), h("p"), h("e"), "");
    expect(await reg.recordCount()).to.equal(2);
    await expect(reg.recordAt(9)).to.be.revertedWithCustomError(reg, "NotFound");
  });
});
