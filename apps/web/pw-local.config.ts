import base from "./playwright.config";

export default { ...base, retries: 0, use: { ...base.use, channel: "chrome" } };
