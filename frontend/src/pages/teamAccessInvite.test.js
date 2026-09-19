/**
 * Regression: Team & Access must not mount the CEO referral card or surface
 * referral-load errors ("User not found") under the empty invite field.
 */
import fs from "fs";
import path from "path";

const pagesDir = path.join(__dirname);
const componentsDir = path.join(__dirname, "..", "components");

describe("Team & Access invite field", () => {
  test("Members does not import or render InviteCeoCard", () => {
    const src = fs.readFileSync(path.join(pagesDir, "Members.jsx"), "utf8");
    expect(src).not.toMatch(/InviteCeoCard/);
    expect(src).not.toMatch(/\/referrals/);
  });

  test("Manage Access includes department lane assignment", () => {
    const src = fs.readFileSync(path.join(pagesDir, "Members.jsx"), "utf8");
    expect(src).toMatch(/member-departments/);
    expect(src).toMatch(/enabled_departments/);
    expect(src).toMatch(/Department lanes/);
  });

  test("InviteCeoCard never pipes raw fetch errors into the link input", () => {
    const src = fs.readFileSync(path.join(componentsDir, "InviteCeoCard.jsx"), "utf8");
    expect(src).not.toMatch(/fetchErrorMessage/);
    expect(src).toMatch(/referral-load-hint/);
    expect(src).toMatch(/setTrackError\(""\)/);
    // Track errors only after a non-empty submit path clears then sets.
    expect(src).toMatch(/if \(!trimmed\)/);
  });
});
