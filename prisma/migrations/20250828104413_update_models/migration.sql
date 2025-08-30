/*
  Warnings:

  - You are about to drop the column `fromDistrict` on the `Order` table. All the data in the column will be lost.
  - You are about to drop the column `fromRegion` on the `Order` table. All the data in the column will be lost.
  - You are about to drop the column `toDistrict` on the `Order` table. All the data in the column will be lost.
  - You are about to drop the column `toRegion` on the `Order` table. All the data in the column will be lost.
  - Added the required column `fromDistrictId` to the `Order` table without a default value. This is not possible if the table is not empty.
  - Added the required column `fromRegionId` to the `Order` table without a default value. This is not possible if the table is not empty.
  - Added the required column `toDistrictId` to the `Order` table without a default value. This is not possible if the table is not empty.
  - Added the required column `toRegionId` to the `Order` table without a default value. This is not possible if the table is not empty.

*/
-- AlterEnum
ALTER TYPE "OrderStatusEnum" ADD VALUE 'processing';

-- AlterTable
ALTER TABLE "Order" DROP COLUMN "fromDistrict",
DROP COLUMN "fromRegion",
DROP COLUMN "toDistrict",
DROP COLUMN "toRegion",
ADD COLUMN     "fromDistrictId" INTEGER NOT NULL,
ADD COLUMN     "fromRegionId" INTEGER NOT NULL,
ADD COLUMN     "toDistrictId" INTEGER NOT NULL,
ADD COLUMN     "toRegionId" INTEGER NOT NULL;

-- CreateTable
CREATE TABLE "Region" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Region_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "District" (
    "id" SERIAL NOT NULL,
    "name" TEXT NOT NULL,
    "regionId" INTEGER NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "District_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "Region_name_key" ON "Region"("name");

-- CreateIndex
CREATE UNIQUE INDEX "District_name_regionId_key" ON "District"("name", "regionId");

-- AddForeignKey
ALTER TABLE "Order" ADD CONSTRAINT "Order_fromRegionId_fkey" FOREIGN KEY ("fromRegionId") REFERENCES "Region"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Order" ADD CONSTRAINT "Order_fromDistrictId_fkey" FOREIGN KEY ("fromDistrictId") REFERENCES "District"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Order" ADD CONSTRAINT "Order_toRegionId_fkey" FOREIGN KEY ("toRegionId") REFERENCES "Region"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Order" ADD CONSTRAINT "Order_toDistrictId_fkey" FOREIGN KEY ("toDistrictId") REFERENCES "District"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "District" ADD CONSTRAINT "District_regionId_fkey" FOREIGN KEY ("regionId") REFERENCES "Region"("id") ON DELETE CASCADE ON UPDATE CASCADE;
