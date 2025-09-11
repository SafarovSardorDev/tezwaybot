/*
  Warnings:

  - You are about to drop the column `email` on the `User` table. All the data in the column will be lost.

*/
-- CreateEnum
CREATE TYPE "OrderType" AS ENUM ('PASSENGER', 'DELIVERY');

-- CreateEnum
CREATE TYPE "PackageType" AS ENUM ('DOCUMENT', 'PARCEL', 'FRAGILE', 'VALUABLE', 'OTHER');

-- CreateEnum
CREATE TYPE "PackageSize" AS ENUM ('SMALL', 'MEDIUM', 'LARGE', 'EXTRA_LARGE');

-- DropIndex
DROP INDEX "User_email_key";

-- AlterTable
ALTER TABLE "Order" ADD COLUMN     "orderType" "OrderType" NOT NULL DEFAULT 'PASSENGER',
ADD COLUMN     "packageDescription" TEXT,
ADD COLUMN     "packageSize" "PackageSize",
ADD COLUMN     "packageType" "PackageType",
ADD COLUMN     "packageWeight" DOUBLE PRECISION,
ADD COLUMN     "receiverName" TEXT,
ADD COLUMN     "receiverPhone" TEXT,
ALTER COLUMN "passengers" DROP NOT NULL,
ALTER COLUMN "departureTime" DROP NOT NULL;

-- AlterTable
ALTER TABLE "User" DROP COLUMN "email";
