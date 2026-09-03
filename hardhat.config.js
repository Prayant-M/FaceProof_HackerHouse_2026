require("@nomicfoundation/hardhat-toolbox");

/**
 * Hardhat exists here ONLY to run the Solidity unit tests and to provide a
 * local chain (`npx hardhat node`). The Python pipeline compiles and deploys
 * with py-solc-x, so nothing at runtime depends on Node.
 *
 * @type import('hardhat/config').HardhatUserConfig
 */
module.exports = {
  solidity: {
    version: "0.8.24",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  paths: {
    sources: "./contracts",
    tests: "./contracts/test",
    cache: "./.hardhat/cache",
    artifacts: "./.hardhat/artifacts",
  },
};
