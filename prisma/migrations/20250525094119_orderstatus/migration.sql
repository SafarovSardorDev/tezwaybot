/*
  Warnings:

  - The values [pending,in_progress,authorized,reversed,on_hold,captured,settled,refunded,charged_back,insufficient_funds,invalid_account_number,expired,communication_error] on the enum `OrderStatusEnum` will be removed. If these variants are still used in the database, this will fail.

*/
-- AlterEnum
BEGIN;
CREATE TYPE "OrderStatusEnum_new" AS ENUM ('initiated', 'completed', 'failed', 'canceled');
ALTER TABLE "OrderStatus" ALTER COLUMN "status" DROP DEFAULT;
ALTER TABLE "OrderStatus" ALTER COLUMN "status" TYPE "OrderStatusEnum_new" USING ("status"::text::"OrderStatusEnum_new");
ALTER TYPE "OrderStatusEnum" RENAME TO "OrderStatusEnum_old";
ALTER TYPE "OrderStatusEnum_new" RENAME TO "OrderStatusEnum";
DROP TYPE "OrderStatusEnum_old";
ALTER TABLE "OrderStatus" ALTER COLUMN "status" SET DEFAULT 'initiated';
COMMIT;
