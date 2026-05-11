import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import FormField from "../FormField";
import Input from "../../atoms/Input";

describe("FormField molecule", () => {
  it("label associates with child input via htmlFor/id", () => {
    render(
      <FormField id="mrn-field" label="診察番号">
        <Input id="mrn-field" />
      </FormField>
    );
    // getByLabelText は label の htmlFor → input の id 経由で解決する
    expect(screen.getByLabelText("診察番号")).toBeInTheDocument();
  });

  it("helper text is rendered when provided", () => {
    render(
      <FormField id="mrn-field" label="診察番号" helper="半角英数字で入力してください">
        <Input id="mrn-field" />
      </FormField>
    );
    expect(screen.getByText("半角英数字で入力してください")).toBeInTheDocument();
  });

  it("error message replaces helper text visually", () => {
    render(
      <FormField
        id="mrn-field"
        label="診察番号"
        helper="半角英数字で入力してください"
        error="診察番号が見つかりません"
      >
        <Input id="mrn-field" error />
      </FormField>
    );
    // エラーが表示される
    expect(screen.getByText("診察番号が見つかりません")).toBeInTheDocument();
    // ヘルパーは表示されない
    expect(screen.queryByText("半角英数字で入力してください")).not.toBeInTheDocument();
  });

  it("error text has text-error class", () => {
    render(
      <FormField id="mrn-field" label="診察番号" error="エラーです">
        <Input id="mrn-field" error />
      </FormField>
    );
    const errorEl = screen.getByText("エラーです");
    expect(errorEl.className).toMatch(/text-error/);
  });

  it("desc element has an id for aria-describedby linkage", () => {
    render(
      <FormField id="mrn-field" label="診察番号" error="エラーです">
        <Input id="mrn-field" error aria-describedby="mrn-field-desc" />
      </FormField>
    );
    expect(document.getElementById("mrn-field-desc")).toBeInTheDocument();
  });

  it("no desc element when neither helper nor error is provided", () => {
    render(
      <FormField id="mrn-field" label="診察番号">
        <Input id="mrn-field" />
      </FormField>
    );
    // role=status の要素が存在しないことを確認
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
